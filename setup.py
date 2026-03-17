from setuptools import setup

package_name = 'ros2yolo'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    install_requires=[
        'opencv-python',
        'numpy',
        'ultralytics',
    ],
    zip_safe=False,
    author='Your Name',
    entry_points={'console_scripts': ['yolo_node = ros2yolo.yolo_node:main', 'convert_to_pose = ros2yolo.convert_to_pose:main']},
)
