from distutils.core import setup
from Cython.Build import cythonize

setup(
  name = 'PPC',
  ext_modules = cythonize(["execute.py", "data_structure.py"]),
)
