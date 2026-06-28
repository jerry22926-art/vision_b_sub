from setuptools import find_packages, setup

package_name = 'vitamin_d'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vitamind',
    maintainer_email='vitamind@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'servo_node = vitamin_d.servo_node:main',
            'sub_gaze_error_node = vitamin_d.sub_gaze_error_node:main',
        ],
    },
)
