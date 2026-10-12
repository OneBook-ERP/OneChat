from setuptools import find_packages, setup

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")


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
