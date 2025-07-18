from setuptools import setup, find_packages

setup(
    name="gum",
    version="0.1.10",
    packages=find_packages(),
    install_requires=[
        # Core dependencies
        "pillow",  # For image processing
        "mss",  # For screen capture
        "pynput",  # For mouse/keyboard monitoring
        "shapely",  # For geometry operations
        "pyobjc-framework-Quartz; sys_platform == 'darwin'",  # For macOS window management
        "openai>=1.0.0",
        "SQLAlchemy>=2.0.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "scikit-learn",
        "aiosqlite",
        "greenlet",
        
        # Web framework and API dependencies
        "fastapi",
        "uvicorn",
        "python-multipart",
        "aiohttp",
        "python-dateutil",
        
        # Additional dependencies for data processing
        "numpy",
    ],
    entry_points={
        'console_scripts': [
            'gum=gum.cli:cli',
        ],
    },
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