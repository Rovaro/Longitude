import os
from unittest import TestCase, mock

from core.caches.base import LongitudeCache
from core.data_sources.base import DataSource, DataSourceQueryConfig, LongitudeQueryResponse, \
    LongitudeWrongQueryException


def load_raw_text(filename):
    file_path = os.path.join(os.path.dirname(__file__), 'raw_text', filename)
    with open(file_path, 'r') as f:
        return f.read()


class TestLongitudeQueryResponse(TestCase):
    def test_preview(self):
        qr = LongitudeQueryResponse(
            rows=[['A' + str(v), 'B' + str(v)] for v in range(20)],
            fields={'As': {'type': 'string'}, 'Bs': {'type': 'string'}},
            profiling={'response_time': 42.0}
        )

        render_top = qr.preview_top()
        expected_render_top = load_raw_text('query_response_render_top.txt')
        self.assertEqual(expected_render_top, render_top)

        render_bottom = qr.preview_bottom()
        expected_render_bottom = load_raw_text('query_response_render_bottom.txt')
        self.assertEqual(expected_render_bottom, render_bottom)


class TestDataSourceQueryConfig(TestCase):
    def test_copy(self):
        a = DataSourceQueryConfig()
        b = a.copy()

        self.assertNotEqual(a, b)
        self.assertEqual(a.__dict__, b.__dict__)


class TestDataSource(TestCase):
    def setUp(self):
        class FakeCache(LongitudeCache):
            @staticmethod
            def generate_key(formatted_query):
                if formatted_query == 'some_query_in_cache':
                    return 'hit'
                return 'miss'

            def setup(self):
                pass

            @property
            def is_ready(self):
                return True

            def execute_get(self, key):
                if key == 'hit':
                    return 'cache hit'
                return None

            def execute_put(self, key, payload):
                return True

        self._cache_class = FakeCache

    def test_cache_must_extend_longitude_cache(self):
        class PoorlyImplementedCache:
            pass

        with self.assertRaises(TypeError):
            DataSource({}, cache_class=PoorlyImplementedCache)

    @mock.patch('core.data_sources.base.is_write_query')
    def test_write_queries_do_not_use_cache(self, is_write_mock):
        ds = DataSource({}, cache_class=self._cache_class)
        ds.setup()
        self.assertTrue(ds.is_ready)

        is_write_mock.return_value = True
        with self.assertRaises(LongitudeWrongQueryException):
            ds.query('some_query')

    @mock.patch('core.data_sources.base.is_write_query')
    @mock.patch('core.data_sources.base.DataSource.parse_response')
    def test_cache_hit(self, parse_response_mock, is_write_mock):
        ds = DataSource({}, cache_class=self._cache_class)
        ds.setup()
        # At high level, ds.query will return a normalized LongitudeQueryResponse
        # In this test we are interested in triggering that call to the parse function that would return such object,
        # but we do not care, in the abstract class, about what content is generated there.
        is_write_mock.return_value = False
        parse_response_mock.return_value = 'normalized cache hit'
        self.assertEqual('normalized cache hit', ds.query('some_query_in_cache'))
        parse_response_mock.assert_called_once_with('cache hit')

    @mock.patch('core.data_sources.base.is_write_query')
    @mock.patch('core.data_sources.base.DataSource.parse_response')
    @mock.patch('core.data_sources.base.DataSource.execute_query')
    def test_cache_miss(self, execute_query_mock, parse_response_mock, is_write_mock):
        ds = DataSource({}, cache_class=self._cache_class)
        ds.setup()
        is_write_mock.return_value = False
        execute_query_mock.return_value = 'some response from the server'
        parse_response_mock.return_value = 'normalized response from data source'
        self.assertEqual('normalized response from data source', ds.query('some_query_not_in_cache'))
        parse_response_mock.assert_called_once_with('some response from the server')

    def test_config(self):
        # Config must be a dictionary
        with self.assertRaises(TypeError):
            DataSource([])
        with self.assertRaises(TypeError):
            DataSource("")
        with self.assertRaises(TypeError):
            DataSource(0)

        # Any values can go in the configuration dictionary but not expected ones trigger a warning
        config = {"some_config_value": 0, "some_another_config_value": "tomato"}
        with self.assertLogs(level='WARNING') as log_test:
            ds = DataSource(config)
            self.assertEqual(log_test.output,
                             ['WARNING:core.data_sources.base:some_another_config_value is an unexpected config value',
                              'WARNING:core.data_sources.base:some_config_value is an unexpected config value'])

        # Values in the config can be retrieved using get_config. If no default or config is defined, None is returned.
        self.assertEqual(0, ds.get_config('some_config_value'))
        self.assertEqual("tomato", ds.get_config('some_another_config_value'))
        self.assertIsNone(ds.get_config('some_random_value_that_does_not_exist_in_config_or_defaults'))

    def test_abstract_methods_are_not_implemented(self):
        ds = DataSource({})

        with self.assertRaises(NotImplementedError):
            ds.query(statement='whatever')

    def test_is_ready(self):
        class FakeReadyCache(LongitudeCache):
            def setup(self):
                pass

            @property
            def is_ready(self):
                return True

        class FakeNotReadyCache(LongitudeCache):
            def setup(self):
                pass

            @property
            def is_ready(self):
                return False

        ds = DataSource(config={}, cache_class=FakeReadyCache)
        self.assertTrue(ds.is_ready)
        ds = DataSource(config={}, cache_class=FakeNotReadyCache)
        self.assertFalse(ds.is_ready)

    def test_copy_default_query_config(self):
        ds = DataSource({})
        the_copy = ds.copy_default_query_config()
        self.assertNotEqual(the_copy, ds._default_query_config)
        self.assertEqual(the_copy.__dict__, ds._default_query_config.__dict__)
