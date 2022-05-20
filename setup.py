from setuptools import find_packages, setup

with open("README.md", "r") as f:
    readme = f.read()

with open("requirements.txt") as requirements_file:
    REQUIREMENTS = [req.strip() for req in requirements_file.readlines()]

setup(
    name="Blogger101",
    version="1.0.0",
    url="https://blogger-101.herokuapp.com",
    license="MIT",
    maintainer="Kethan Vegunta",
    maintainer_email="kethan@vegunta.com",
    description="A full-fledged blogging application",
    long_description=readme,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=REQUIREMENTS,
    extras_require={"test": ["pytest", "coverage"]},
)
