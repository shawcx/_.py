all:
	@#

install: all
	pip3 install --upgrade .

dist: all
	@./setup.py sdist

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} +

distclean: clean
	@rm -rf build/ dist/ *.egg-info/
