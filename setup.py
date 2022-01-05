import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dkbparse",
    version="0.0.1",
    author="Robert Walter",
    description="PDF parser for DKB bank and VISA statements",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/robbeofficial/dkbparse",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    entry_points = {
        'console_scripts': [
            'dkbparse = dkbparse.dkbparse:main',
        ]
    },
)