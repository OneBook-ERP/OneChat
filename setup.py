from setuptools import find_packages, setup

install_requires = [
    "python-magic",
    "anthropic",
    "openai",
]


from onechat import __version__ as version

setup(
    name="onechat",
    version=version,
    description="WhatsApp integration for frappe",
    author="Leo Daniel A",
    author_email="daniel@onebook.app",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
