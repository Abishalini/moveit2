import os
import yaml
import unittest
import launch
import launch_testing.actions
import launch_testing.asserts

from launch import LaunchDescription
from launch.some_substitutions_type import SomeSubstitutionsType
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

from ament_index_python.packages import get_package_share_directory

from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

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


def generate_servo_test_description(*args,
                                    gtest_name: SomeSubstitutionsType,
                                    start_position_path: SomeSubstitutionsType = '../config/start_positions.yaml'):

    # Get URDF and SRDF
    robot_description_config = load_file('moveit_resources_panda_description', 'urdf/panda.urdf')
    robot_description = {'robot_description' : robot_description_config}

    robot_description_semantic_config = load_file('moveit_resources_panda_moveit_config', 'config/panda.srdf')
    robot_description_semantic = {'robot_description_semantic' : robot_description_semantic_config}

    # Get parameters for the Pose Tracking node
    pose_tracking_yaml = load_yaml('moveit_servo', 'config/pose_tracking_settings.yaml')
    pose_tracking_params = { 'moveit_servo' : pose_tracking_yaml }

    # Get parameters for the Servo node
    servo_yaml = load_yaml('moveit_servo', 'config/panda_simulated_config_pose_tracking.yaml')
    servo_params = { 'moveit_servo' : servo_yaml }

    kinematics_yaml = load_yaml('moveit_resources_panda_moveit_config', 'config/kinematics.yaml')

    # Publishes tf's for the robot
    # robot_state_publisher = Node(
    #     package='robot_state_publisher',
    #     executable='robot_state_publisher',
    #     output='screen',
    #     parameters=[robot_description]
    # )

    # RViz
    # rviz_config_file = get_package_share_directory('moveit_servo') + "/config/demo_rviz_pose_tracking.rviz"
    # rviz_node = Node(package='rviz2',
    #                  executable='rviz2',
    #                  name='rviz2',
    #                  #prefix=['xterm -e gdb -ex run --args'],
    #                  output='log',
    #                  arguments=['-d', rviz_config_file],
    #                  parameters=[robot_description, robot_description_semantic, kinematics_yaml])

    # A node to publish world -> panda_link0 transform
    # static_tf = Node(package='tf2_ros',
    #                  executable='static_transform_publisher',
    #                  name='static_transform_publisher',
    #                  output='log',
    #                  arguments=['0.0', '0.0', '0.0', '0.0', '0.0', '0.0', 'world', 'panda_link0'])

    # Fake joint driver
    fake_joint_driver_node = Node(package='fake_joint_driver',
                                  executable='fake_joint_driver_node',
                                  parameters=[{'controller_name': 'fake_joint_trajectory_controller'},
                                              os.path.join(get_package_share_directory("moveit_servo"), "config", "panda_controllers.yaml"),
                                              os.path.join(get_package_share_directory("moveit_servo"), "config", "start_positions.yaml"),
                                              robot_description]
                                )
    
    # pose_tracking_node = Node(
    #     package='moveit_servo',
    #     executable='servo_pose_tracking_demo',
    #     #prefix=['xterm -e gdb -ex run --args'],
    #     output='screen',
    #     parameters=[robot_description, robot_description_semantic, kinematics_yaml, pose_tracking_params, servo_params]
    # )
    # Component nodes for tf and Servo
    test_container = ComposableNodeContainer(
            name='test_pose_tracking_container',
            namespace='/',
            package='rclcpp_components',
            executable='component_container',
            composable_node_descriptions=[
                ComposableNode(
                    package='robot_state_publisher',
                    plugin='robot_state_publisher::RobotStatePublisher',
                    name='robot_state_publisher',
                    parameters=[robot_description]),
                ComposableNode(
                    package='tf2_ros',
                    plugin='tf2_ros::StaticTransformBroadcasterNode',
                    name='static_tf2_broadcaster',
                    parameters=[ {'/child_frame_id' : 'panda_link0', '/frame_id' : 'world'} ]),
                ComposableNode(
                    package='moveit_servo',
                    plugin='moveit_servo::PoseTracking',
                    name='pose_tracking',
                    parameters=[pose_tracking_params, servo_params, robot_description, robot_description_semantic, kinematics_yaml])
                    #extra_arguments=[{'use_intra_process_comm': True}])
            ],
            output='screen',
    )

    pose_tracking_gtest = launch_testing.actions.GTest(
                path=PathJoinSubstitution([LaunchConfiguration('test_binary_dir'), gtest_name]),
                timeout=40.0, output='screen'
        )

    #return LaunchDescription([static_tf, fake_joint_driver_node, robot_state_publisher])
    return launch.LaunchDescription([
        launch.actions.DeclareLaunchArgument(name='test_binary_dir',
                                             description='Binary directory of package '
                                                         'containing test executables'),
        fake_joint_driver_node,
        #robot_state_publisher,
        #static_tf,
        #rviz_node,
        test_container,
        pose_tracking_gtest,
        launch_testing.actions.ReadyToTest()
    ]), {'test_container': test_container ,'servo_gtest': pose_tracking_gtest, 'fake_joint_driver_node': fake_joint_driver_node }
    #{'robot_stablte_puisher': robot_state_publisher, 'static_tf': static_tf, 'servo_gtest': pose_tracking_gtest, 'fake_joint_driver_node': fake_joint_driver_node }


def generate_test_description():
    return generate_servo_test_description(gtest_name='test_servo_pose_tracking',
                                           start_position_path='../config/collision_start_positions.yaml')


class TestGTestProcessActive(unittest.TestCase):

    def test_gtest_run_complete(self, proc_info, test_container, servo_gtest, fake_joint_driver_node):
        proc_info.assertWaitForShutdown(servo_gtest, timeout=4000.0)


@launch_testing.post_shutdown_test()
class TestGTestProcessPostShutdown(unittest.TestCase):

    def test_gtest_pass(self, proc_info, test_container, servo_gtest, fake_joint_driver_node):
        launch_testing.asserts.assertExitCodes(proc_info, process=servo_gtest)
