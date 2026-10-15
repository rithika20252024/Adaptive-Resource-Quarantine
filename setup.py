from setuptools import setup, find_packages

setup(
    name="adaptive-resource-quarantine",
    version="1.0.0",
    author="Rithika S, K. Vaishnavi",
    author_email="rithika20252024@gmail.com",
    description="Adaptive Resource Quarantine for Protecting Operating Systems Against Abnormal Process Behavior",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/rithika20252024/Adaptive-Resource-Quarantine",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Topic :: System :: Operating System",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "arq=arq.cli:main",
        ],
    },
)
