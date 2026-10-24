PYTHON    ?= python3
DEB_IMAGE ?= debian:trixie
VERSION    = $(shell sed -n "s/^__version__ *= *'\(.*\)'/\1/p" _/version.py)

all:
	@#

test:
	$(PYTHON) -m pytest tests

install: all
	pip3 install --upgrade .

develop:
	pip3 install --editable '.[all,test]'

dist: all
	python3 -m build

# builds python3-underscorepy in a $(DEB_IMAGE) container, from the files
# git tracks or would track, and leaves it in deb_dist/
deb:
	@head -1 debian/changelog | grep -qF '($(VERSION))' || \
		{ echo 'debian/changelog needs an entry for $(VERSION)' >&2; exit 1; }
	@rm -rf deb_dist/ && mkdir deb_dist
	git ls-files -co --exclude-standard | tar -cf - --ignore-failed-read -T - | \
	docker run --rm -i $(DEB_IMAGE) sh -c ' \
		mkdir -p /build/src && tar -xf - -C /build/src && cd /build/src && \
		{ apt-get update && apt-get install -y --no-install-recommends lintian && \
		  apt-get build-dep -y ./ && dpkg-buildpackage -b -us -uc && \
		  lintian --fail-on error ../*.deb; } >&2 && \
		cd /build && tar -cf - *.deb' | tar -xf - -C deb_dist
	@ls deb_dist/*.deb

clean:
	@find . -type d -name __pycache__ -exec rm -rf {} +

distclean: clean
	@rm -rf build/ dist/ deb_dist/ *.egg-info/
