from setuptools import setup, find_packages
import os

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="updatelan5",
    version="1.0.0",
    description="Ứng dụng quản lý biểu mẫu và tạo tài liệu",
    author="Author",
    author_email="author@example.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'updatelan5=app:run_app',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
)