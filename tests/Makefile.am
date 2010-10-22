TESTS_ENVIRONMENT = RP210_SPEC_PATH=@top_srcdir@/data/RP210v10-pub-20070121-1600.csv PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=@top_builddir@/:@top_builddir@/tests:@top_srcdir@/tests python
dist_check_SCRIPTS = \
	test_avid.py \
	test_common.py \
	test_s377m.py \
	test_rp210types.py

nobase_dist_check_DATA = $(wildcard $(srcdir)/data/*.raw)

TESTS = $(dist_check_SCRIPTS)

CLEANFILES = $(wildcard $(builddir)/*.new)
