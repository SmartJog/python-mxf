mxfdir = $(pyexecdir)/mxf
mxf_PYTHON = \
	__init__.py \
	avid.py \
	common.py \
	parser.py \
	rp210types.py \
	s377m.py

nodist_mxf_PYTHON = rp210.py

edit = $(SED) \
	-e 's|@pkgdatadir[@]|$(pkgdatadir)|g'

$(nodist_mxf_PYTHON): $(nodist_mxf_PYTHON:=.in) Makefile
	$(edit) $(srcdir)/$@.in > $(builddir)/$@

check-local:
	-for item in $(wildcard $(srcdir)/*.py); do \
		$(LN_S) $(srcdir)/$$item $(top_builddir)/mxf/ 2> /dev/null; \
	done

BUILT_SOURCES = $(nodist_mxf_PYTHON)
CLEANFILES = $(mxf_PYTHON:.py=.pyc) $(BUILT_SOURCES)
EXTRA_DIST = $(nodist_mxf_PYTHON:=.in)
