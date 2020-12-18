import os
import yaml
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def load_file(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path, 'r') as file:
            return file.read()
    except EnvironmentError: # parent of IOError, OSError *and* WindowsError where available
        return None

def load_yaml(package_name, file_path):
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)

    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except EnvironmentError: # parent of IOError, OSError *and* WindowsError where available
        return None


def generate_launch_description():

    # Get URDF and SRDF
    robot_description_config = load_file('moveit_resources_panda_description', 'urdf/panda.urdf')
    robot_description = {'robot_description' : robot_description_config}

    robot_description_semantic_config = load_file('moveit_resources_panda_moveit_config', 'config/panda.srdf')
    robot_description_semantic = {'robot_description_semantic' : robot_description_semantic_config}

    # Get parameters for the Pose Tracking node
    pose_tracking_yaml = load_yaml('moveit_servo', 'config/pose_tracking_settings.yaml')
    pose_tracking_params = { 'moveit_servo' : pose_tracking_yaml }

    panda_simulated_yaml = load_yaml('moveit_servo', 'config/panda_simulated_config.yaml')
    panda_simulated_params = { 'moveit_servo' : panda_simulated_yaml }

    panda_kinematics_yaml = load_yaml('moveit_resources_panda_moveit_config', 'config/kinematics.yaml')
    panda_kinematics_params = {'robot_description_kinematics' : panda_kinematics_yaml }

    #RViz
    rviz_config_file = get_package_share_directory('moveit_servo') + "/config/demo_rviz_config.rviz"
    rviz_node = Node(package='rviz2',
                     executable='rviz2',
                     name='rviz2',
                     #prefix=['xterm -e gdb -ex run --args'],
                     output='log',
                     arguments=['-d', rviz_config_file],
                     parameters=[robot_description, robot_description_semantic, panda_kinematics_params])


    pose_tracking_node = Node(
        package='moveit_servo',
        executable='servo_pose_tracking_demo',
        prefix=['xterm -e gdb -ex run --args'],
        output='screen',
        parameters=[pose_tracking_params, panda_simulated_params, robot_description, robot_description_semantic, panda_kinematics_params]
    )

    # Fake joint driver
    fake_joint_driver_node = Node(package='fake_joint_driver',
                                  executable='fake_joint_driver_node',
                                  # TODO(JafarAbdi): Why this launch the two nodes (controller manager and the fake joint driver) with the same name!
                                  # name='fake_joint_driver_node',
                                  parameters=[{'controller_name': 'panda_arm_controller'},
                                              os.path.join(get_package_share_directory("run_moveit_cpp"), "config", "panda_controllers.yaml"),
                                              os.path.join(get_package_share_directory("run_moveit_cpp"), "config", "start_positions.yaml"),
                                              robot_description]
                                  )

    return LaunchDescription([ pose_tracking_node, rviz_node, fake_joint_driver_node ])