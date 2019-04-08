import pytest
import numpy as np
import pandas.util.testing as pdt

import ixmp
from ixmp.testing import dantzig_transport, TS_DF, HIST_DF


def test_run_clone(tmpdir, test_data_path):
    # this test is designed to cover the full functionality of the GAMS API
    # - creates a new scenario and exports a gdx file
    # - runs the tutorial transport model
    # - reads back the solution from the output
    # - performs the test on the objective value
    mp = ixmp.Platform(tmpdir, dbtype='HSQLDB')
    scen = dantzig_transport(mp, solve=test_data_path)
    assert np.isclose(scen.var('z')['lvl'], 153.675)

    # cloning with `keep_solution=True` keeps all timeseries and the solution
    scen2 = scen.clone(keep_solution=True)
    assert np.isclose(scen2.var('z')['lvl'], 153.675)
    obs = scen2.timeseries(iamc=True)
    pdt.assert_frame_equal(obs, TS_DF)

    # cloning with `keep_solution=True` and `first_model_year` raises an error
    pytest.raises(ValueError, scen.clone, first_model_year=2005)

    # cloning with `keep_solution=False` drops the solution and only keeps
    # timeseries set as `meta=True`
    scen3 = scen.clone(keep_solution=False)
    assert np.isnan(scen3.var('z')['lvl'])
    obs = scen3.timeseries(iamc=True)
    pdt.assert_frame_equal(obs, HIST_DF)

    # cloning with `keep_solution=False` and `first_model_year`
    # drops the solution and removes all timeseries not marked `meta=True`
    # in the model horizon (i.e, `year >= first_model_year`)
    scen4 = scen.clone(keep_solution=False, first_model_year=2005)
    assert np.isnan(scen4.var('z')['lvl'])
    obs = scen4.timeseries(iamc=True)
    exp = TS_DF.copy()
    exp.loc[0, 2005] = np.nan
    pdt.assert_frame_equal(obs, exp)


def scenario_list(mp):
    return mp.scenario_list(default=False)[['model', 'scenario']]


def assert_multi_db(mp1, mp2):
    pdt.assert_frame_equal(scenario_list(mp1), scenario_list(mp2))


def test_multi_db_run(tmpdir, test_data_path):
    mp1 = ixmp.Platform(tmpdir / 'mp1', dbtype='HSQLDB')
    scen1 = make_dantzig(mp1, solve=test_data_path)

    mp2 = ixmp.Platform(tmpdir / 'mp2', dbtype='HSQLDB')
    # add other unit to make sure that the mapping is correct during clone
    mp2.add_unit('wrong_unit')
    mp2.add_region('wrong_region', 'country')

    scen2 = scen1.clone(platform=mp2, keep_solution=False)
    assert np.isnan(scen2.var('z')['lvl'])
    scen2.solve(model=str(test_data_path / 'transport_ixmp'))
    assert scen1.var('z') == scen2.var('z')
    assert_multi_db(mp1, mp2)

    # check that custom unit and region are migrated correctly
    assert scen2.par('f')['value'] == 90.0
    assert scen2.par('f')['unit'] == 'USD_per_km'
    obs = scen2.timeseries(iamc=True)
    pdt.assert_frame_equal(obs, TS_DF, check_dtype=False)


def test_multi_db_edit_source(tmpdir):
    mp1 = ixmp.Platform(tmpdir / 'mp1', dbtype='HSQLDB')
    scen1 = make_dantzig(mp1)

    mp2 = ixmp.Platform(tmpdir / 'mp2', dbtype='HSQLDB')
    scen2 = scen1.clone(platform=mp2)

    pdt.assert_frame_equal(scen1.par('d'), scen2.par('d'))

    scen1.check_out()
    scen1.add_par('d', ['san-diego', 'topeka'], 1.5, 'km')
    scen1.commit('foo')

    obs = (scen1
           .par('d')
           .set_index(['i', 'j'])
           .loc['san-diego', 'topeka']
           ['value']
           )
    exp = 1.5
    assert np.isclose(obs, exp)

    obs = (scen2
           .par('d')
           .set_index(['i', 'j'])
           .loc['san-diego', 'topeka']
           ['value']
           )
    exp = 1.4
    assert np.isclose(obs, exp)

    assert_multi_db(mp1, mp2)


def test_multi_db_edit_target(tmpdir):
    mp1 = ixmp.Platform(tmpdir / 'mp1', dbtype='HSQLDB')
    scen1 = make_dantzig(mp1)

    mp2 = ixmp.Platform(tmpdir / 'mp2', dbtype='HSQLDB')
    scen2 = scen1.clone(platform=mp2)

    pdt.assert_frame_equal(scen1.par('d'), scen2.par('d'))

    scen2.check_out()
    scen2.add_par('d', ['san-diego', 'topeka'], 1.5, 'km')
    scen2.commit('foo')

    obs = (scen2
           .par('d')
           .set_index(['i', 'j'])
           .loc['san-diego', 'topeka']
           ['value']
           )
    exp = 1.5
    assert np.isclose(obs, exp)

    obs = (scen1
           .par('d')
           .set_index(['i', 'j'])
           .loc['san-diego', 'topeka']
           ['value']
           )
    exp = 1.4
    assert np.isclose(obs, exp)

    assert_multi_db(mp1, mp2)
