from setuptools import setup, find_packages

setup(
    name='ml4cvd',
    version='0.0.1',
    description='Machine Learning for Disease',
    url='https://github.com/broadinstitute/ml',
    python_requires='>=3.6',
    install_requires=["numpy", "pandas", "h5py", "keras", "scipy", "numcodecs", "xmltodict", "pytest", "sklearn", 
        "pydot==1.2.4", "keras-rectified-adam==0.10.0", "nibabel==2.5.0", "pydicom==1.2.2", 
        "hyperopt==0.1.2", "protobuf==3.7.1", "seaborn==0.9.0", "biosppy", "vtk==8.1.2",
        "imageio==2.6.1", "apache-beam[gcp]==2.12.0", "google-cloud-storage==1.13.0", "ipywidgets==7.5.1", "bokeh",
        "keras_radam"],
    packages=find_packages(),
)
