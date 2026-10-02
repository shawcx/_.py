all:
	@#

install: all
	pip3 install --upgrade .

develop:
	pip3 install --editable '.[all]'

dist: all
	python3 -m build

deb:
	@rm -rf deb_dist/
	python3 setup.py --command-packages=stdeb.command bdist_deb

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} +

distclean: clean
	@rm -rf build/ dist/ deb_dist/ *.egg-info/
