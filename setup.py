from setuptools import setup, find_packages

setup(
    name="gum",
    version="0.1.1",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # Core dependencies
        "pillow",  # For image processing
        "mss",  # For screen capture
        "pynput",  # For mouse/keyboard monitoring
        "shapely",  # For geometry operations
        "pyobjc-framework-Quartz",  # For macOS window management
        "openai>=1.0.0",
        "SQLAlchemy>=2.0.0",
        "pydantic>=2.0.0",
        "sqlalchemy-utils>=0.41.0",
        "python-dotenv>=1.0.0",
        "scikit-learn",
        "aiosqlite",
        "greenlet"
    ],
    author="Omar Shaikh",
    author_email="oshaikh13@gmail.com",
    description="A Python package with command-line interface",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/GeneralUserModels/gum",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
) 