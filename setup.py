from setuptools import setup, find_packages

setup(
    name='ml4cvd',
    version='0.0.1',
    description='Machine Learning for Disease',
    url='https://github.com/broadinstitute/ml',
    python_requires='>=3.6',
    install_requires=["numpy", "pandas", "h5py", "keras", "scipy", "numcodecs", "xmltodict", "pytest", "sklearn", "vtk", "pydicom", "nibabel", "imageio", "seaborn", "biosppy", "google-cloud-bigquery", "keras_radam"],
    packages=find_packages(),
)
