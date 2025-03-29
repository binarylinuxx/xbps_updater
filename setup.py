from setuptools import setup, find_packages

setup(
    name='xbps_updater',
    version='1.0',
    packages=find_packages(),
    install_requires=[
        'python3',
        'python3-gobject',
    ],
    entry_points={
        'console_scripts': [
            'xbps_updater=xbps_updater:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['README.md', 'install.sh', 'run', 'xbps_updater.desktop'],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
