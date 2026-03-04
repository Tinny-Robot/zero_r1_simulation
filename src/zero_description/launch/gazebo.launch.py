import os
import subprocess
import tempfile
from pathlib import Path
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    OpaqueFunction,
    SetEnvironmentVariable,
    SetLaunchConfiguration,
    TimerAction,
)
from launch.substitutions import Command, EnvironmentVariable, LaunchConfiguration

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _render_xacro_to_urdf(context):
    model_path = LaunchConfiguration("model").perform(context)
    result = subprocess.run(["xacro", model_path], check=True, capture_output=True, text=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".urdf", delete=False) as urdf_file:
        urdf_file.write(result.stdout)
        rendered_urdf_path = urdf_file.name

    return [SetLaunchConfiguration("generated_urdf", rendered_urdf_path)]


def generate_launch_description():
    zero_description = get_package_share_directory("zero_description")

    model_arg = DeclareLaunchArgument(name="model", default_value=os.path.join(
                                        zero_description, "urdf", "zero.urdf.xacro"
                                        ),
                                      description="Absolute path to robot urdf file"
    )

    world_arg = DeclareLaunchArgument(
        name="world",
        default_value="empty.sdf",
        description="World file to load in gz sim"
    )

    world_name_arg = DeclareLaunchArgument(
        name="world_name",
        default_value="empty",
        description="World name used for /world/<name>/create service"
    )

    robot_name_arg = DeclareLaunchArgument(
        name="robot_name",
        default_value="zero",
        description="Name assigned to the spawned robot entity"
    )

    spawn_z_arg = DeclareLaunchArgument(
        name="spawn_z",
        default_value="0.1271",
        description="Initial robot spawn z offset"
    )

    gazebo_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=[
            str(Path(zero_description).parent.resolve())
            ]
        )

    gazebo_system_plugin_path = SetEnvironmentVariable(
        name="GZ_SIM_SYSTEM_PLUGIN_PATH",
        value=[
            EnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", default_value=""),
            os.pathsep,
            "/opt/ros/humble/lib",
        ],
    )
    
    robot_description = ParameterValue(Command([
            "xacro ",
            LaunchConfiguration("model")
        ]),
        value_type=str
    )

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"robot_description": robot_description,
                     "use_sim_time": True}]
    )

    render_urdf = OpaqueFunction(function=_render_xacro_to_urdf)

    gazebo = ExecuteProcess(
        cmd=["gz", "sim", "-v", "4", "-r", LaunchConfiguration("world")],
        output="screen"
    )

    gz_spawn_entity = TimerAction(
        period=2.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    "gz", "service",
                    "-s", ["/world/", LaunchConfiguration("world_name"), "/create"],
                    "--reqtype", "gz.msgs.EntityFactory",
                    "--reptype", "gz.msgs.Boolean",
                    "--timeout", "5000",
                    "--req",
                    [
                        'sdf_filename: "',
                        LaunchConfiguration("generated_urdf"),
                        '" name: "',
                        LaunchConfiguration("robot_name"),
                        '" pose: { position: { z: ',
                        LaunchConfiguration("spawn_z"),
                        ' } }',
                    ],
                ],
                output="screen",
            )
        ],
    )


    return LaunchDescription([
        model_arg,
        world_arg,
        world_name_arg,
        robot_name_arg,
        spawn_z_arg,
        gazebo_resource_path,
        gazebo_system_plugin_path,
        render_urdf,
        robot_state_publisher_node,
        gazebo,
        gz_spawn_entity,
    ])