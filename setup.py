from setuptools import setup, find_packages

setup(
    name='nanojekyll',
    version='0.1.0',
    description='A minimal static site generator. Certified free from Ruby.',
    author='Tizian Zeltner',
    packages=find_packages(include=['nanojekyll', 'nanojekyll.*']),
    install_requires=[
        'liquidpy',
        'markdown',
        'pyyaml'
    ],
    entry_points={
        'console_scripts': ['nanojekyll=nanojekyll.nanojekyll:main']
    }
)
