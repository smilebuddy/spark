#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import sys
import json

if sys.version >= '3':
    intlike = int
    basestring = unicode = str
else:
    intlike = (int, long)

from abc import ABCMeta, abstractmethod

from pyspark import since, keyword_only
from pyspark.rdd import ignore_unicode_prefix
from pyspark.sql.readwriter import OptionUtils, to_str
from pyspark.sql.types import *

__all__ = ["StreamingQuery", "StreamingQueryManager", "DataStreamReader", "DataStreamWriter"]


class StreamingQuery(object):
    """
    A handle to a query that is executing continuously in the background as new data arrives.
    All these methods are thread-safe.

    .. note:: Experimental

    .. versionadded:: 2.0
    """

    def __init__(self, jsq):
        self._jsq = jsq

    @property
    @since(2.0)
    def id(self):
        """The id of the streaming query.
        """
        return self._jsq.id().toString()

    @property
    @since(2.0)
    def name(self):
        """The name of the streaming query. This name is unique across all active queries.
        """
        return self._jsq.name()

    @property
    @since(2.0)
    def isActive(self):
        """Whether this streaming query is currently active or not.
        """
        return self._jsq.isActive()

    @since(2.0)
    def awaitTermination(self, timeout=None):
        """Waits for the termination of `this` query, either by :func:`query.stop()` or by an
        exception. If the query has terminated with an exception, then the exception will be thrown.
        If `timeout` is set, it returns whether the query has terminated or not within the
        `timeout` seconds.

        If the query has terminated, then all subsequent calls to this method will either return
        immediately (if the query was terminated by :func:`stop()`), or throw the exception
        immediately (if the query has terminated with exception).

        throws :class:`StreamingQueryException`, if `this` query has terminated with an exception
        """
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout < 0:
                raise ValueError("timeout must be a positive integer or float. Got %s" % timeout)
            return self._jsq.awaitTermination(int(timeout * 1000))
        else:
            return self._jsq.awaitTermination()

    @property
    @since(2.1)
    def status(self):
        """
        Returns the current status of the query.
        """
        return json.loads(self._jsq.status().json())

    @property
    @since(2.1)
    def recentProgresses(self):
        """Returns an array of the most recent [[StreamingQueryProgress]] updates for this query.
        The number of progress updates retained for each stream is configured by Spark session
        configuration `spark.sql.streaming.numRecentProgresses`.
        """
        return [json.loads(p.json()) for p in self._jsq.recentProgresses()]

    @property
    @since(2.1)
    def lastProgress(self):
        """
        Returns the most recent :class:`StreamingQueryProgress` update of this streaming query.
        :return: a map
        """
        return json.loads(self._jsq.lastProgress().json())

    @since(2.0)
    def processAllAvailable(self):
        """Blocks until all available data in the source has been processed and committed to the
        sink. This method is intended for testing.

        .. note:: In the case of continually arriving data, this method may block forever.
            Additionally, this method is only guaranteed to block until data that has been
            synchronously appended data to a stream source prior to invocation.
            (i.e. `getOffset` must immediately reflect the addition).
        """
        return self._jsq.processAllAvailable()

    @since(2.0)
    def stop(self):
        """Stop this streaming query.
        """
        self._jsq.stop()


class StreamingQueryManager(object):
    """A class to manage all the :class:`StreamingQuery` StreamingQueries active.

    .. note:: Experimental

    .. versionadded:: 2.0
    """

    def __init__(self, jsqm):
        self._jsqm = jsqm

    @property
    @ignore_unicode_prefix
    @since(2.0)
    def active(self):
        """Returns a list of active queries associated with this SQLContext

        >>> sq = sdf.writeStream.format('memory').queryName('this_query').start()
        >>> sqm = spark.streams
        >>> # get the list of active streaming queries
        >>> [q.name for q in sqm.active]
        [u'this_query']
        >>> sq.stop()
        """
        return [StreamingQuery(jsq) for jsq in self._jsqm.active()]

    @ignore_unicode_prefix
    @since(2.0)
    def get(self, id):
        """Returns an active query from this SQLContext or throws exception if an active query
        with this name doesn't exist.

        >>> sq = sdf.writeStream.format('memory').queryName('this_query').start()
        >>> sq.name
        u'this_query'
        >>> sq = spark.streams.get(sq.id)
        >>> sq.isActive
        True
        >>> sq = sqlContext.streams.get(sq.id)
        >>> sq.isActive
        True
        >>> sq.stop()
        """
        return StreamingQuery(self._jsqm.get(id))

    @since(2.0)
    def awaitAnyTermination(self, timeout=None):
        """Wait until any of the queries on the associated SQLContext has terminated since the
        creation of the context, or since :func:`resetTerminated()` was called. If any query was
        terminated with an exception, then the exception will be thrown.
        If `timeout` is set, it returns whether the query has terminated or not within the
        `timeout` seconds.

        If a query has terminated, then subsequent calls to :func:`awaitAnyTermination()` will
        either return immediately (if the query was terminated by :func:`query.stop()`),
        or throw the exception immediately (if the query was terminated with exception). Use
        :func:`resetTerminated()` to clear past terminations and wait for new terminations.

        In the case where multiple queries have terminated since :func:`resetTermination()`
        was called, if any query has terminated with exception, then :func:`awaitAnyTermination()`
        will throw any of the exception. For correctly documenting exceptions across multiple
        queries, users need to stop all of them after any of them terminates with exception, and
        then check the `query.exception()` for each query.

        throws :class:`StreamingQueryException`, if `this` query has terminated with an exception
        """
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout < 0:
                raise ValueError("timeout must be a positive integer or float. Got %s" % timeout)
            return self._jsqm.awaitAnyTermination(int(timeout * 1000))
        else:
            return self._jsqm.awaitAnyTermination()

    @since(2.0)
    def resetTerminated(self):
        """Forget about past terminated queries so that :func:`awaitAnyTermination()` can be used
        again to wait for new terminations.

        >>> spark.streams.resetTerminated()
        """
        self._jsqm.resetTerminated()


class Trigger(object):
    """Used to indicate how often results should be produced by a :class:`StreamingQuery`.

    .. note:: Experimental

    .. versionadded:: 2.0
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def _to_java_trigger(self, sqlContext):
        """Internal method to construct the trigger on the jvm.
        """
        pass


class ProcessingTime(Trigger):
    """A trigger that runs a query periodically based on the processing time. If `interval` is 0,
    the query will run as fast as possible.

    The interval should be given as a string, e.g. '2 seconds', '5 minutes', ...

    .. note:: Experimental

    .. versionadded:: 2.0
    """

    def __init__(self, interval):
        if type(interval) != str or len(interval.strip()) == 0:
            raise ValueError("interval should be a non empty interval string, e.g. '2 seconds'.")
        self.interval = interval

    def _to_java_trigger(self, sqlContext):
        return sqlContext._sc._jvm.org.apache.spark.sql.streaming.ProcessingTime.create(
            self.interval)


class DataStreamReader(OptionUtils):
    """
    Interface used to load a streaming :class:`DataFrame` from external storage systems
    (e.g. file systems, key-value stores, etc). Use :func:`spark.readStream`
    to access this.

    .. note:: Experimental.

    .. versionadded:: 2.0
    """

    def __init__(self, spark):
        self._jreader = spark._ssql_ctx.readStream()
        self._spark = spark

    def _df(self, jdf):
        from pyspark.sql.dataframe import DataFrame
        return DataFrame(jdf, self._spark)

    @since(2.0)
    def format(self, source):
        """Specifies the input data source format.

        .. note:: Experimental.

        :param source: string, name of the data source, e.g. 'json', 'parquet'.

        >>> s = spark.readStream.format("text")
        """
        self._jreader = self._jreader.format(source)
        return self

    @since(2.0)
    def schema(self, schema):
        """Specifies the input schema.

        Some data sources (e.g. JSON) can infer the input schema automatically from data.
        By specifying the schema here, the underlying data source can skip the schema
        inference step, and thus speed up data loading.

        .. note:: Experimental.

        :param schema: a :class:`pyspark.sql.types.StructType` object

        >>> s = spark.readStream.schema(sdf_schema)
        """
        from pyspark.sql import SparkSession
        if not isinstance(schema, StructType):
            raise TypeError("schema should be StructType")
        spark = SparkSession.builder.getOrCreate()
        jschema = spark._jsparkSession.parseDataType(schema.json())
        self._jreader = self._jreader.schema(jschema)
        return self

    @since(2.0)
    def option(self, key, value):
        """Adds an input option for the underlying data source.

        .. note:: Experimental.

        >>> s = spark.readStream.option("x", 1)
        """
        self._jreader = self._jreader.option(key, to_str(value))
        return self

    @since(2.0)
    def options(self, **options):
        """Adds input options for the underlying data source.

        .. note:: Experimental.

        >>> s = spark.readStream.options(x="1", y=2)
        """
        for k in options:
            self._jreader = self._jreader.option(k, to_str(options[k]))
        return self

    @since(2.0)
    def load(self, path=None, format=None, schema=None, **options):
        """Loads a data stream from a data source and returns it as a :class`DataFrame`.

        .. note:: Experimental.

        :param path: optional string for file-system backed data sources.
        :param format: optional string for format of the data source. Default to 'parquet'.
        :param schema: optional :class:`pyspark.sql.types.StructType` for the input schema.
        :param options: all other string options

        >>> json_sdf = spark.readStream.format("json") \\
        ...     .schema(sdf_schema) \\
        ...     .load(tempfile.mkdtemp())
        >>> json_sdf.isStreaming
        True
        >>> json_sdf.schema == sdf_schema
        True
        """
        if format is not None:
            self.format(format)
        if schema is not None:
            self.schema(schema)
        self.options(**options)
        if path is not None:
            if type(path) != str or len(path.strip()) == 0:
                raise ValueError("If the path is provided for stream, it needs to be a " +
                                 "non-empty string. List of paths are not supported.")
            return self._df(self._jreader.load(path))
        else:
            return self._df(self._jreader.load())

    @since(2.0)
    def json(self, path, schema=None, primitivesAsString=None, prefersDecimal=None,
             allowComments=None, allowUnquotedFieldNames=None, allowSingleQuotes=None,
             allowNumericLeadingZero=None, allowBackslashEscapingAnyCharacter=None,
             mode=None, columnNameOfCorruptRecord=None, dateFormat=None,
             timestampFormat=None):
        """
        Loads a JSON file stream (`JSON Lines text format or newline-delimited JSON
        <http://jsonlines.org/>`_) and returns a :class`DataFrame`.

        If the ``schema`` parameter is not specified, this function goes
        through the input once to determine the input schema.

        .. note:: Experimental.

        :param path: string represents path to the JSON dataset,
                     or RDD of Strings storing JSON objects.
        :param schema: an optional :class:`pyspark.sql.types.StructType` for the input schema.
        :param primitivesAsString: infers all primitive values as a string type. If None is set,
                                   it uses the default value, ``false``.
        :param prefersDecimal: infers all floating-point values as a decimal type. If the values
                               do not fit in decimal, then it infers them as doubles. If None is
                               set, it uses the default value, ``false``.
        :param allowComments: ignores Java/C++ style comment in JSON records. If None is set,
                              it uses the default value, ``false``.
        :param allowUnquotedFieldNames: allows unquoted JSON field names. If None is set,
                                        it uses the default value, ``false``.
        :param allowSingleQuotes: allows single quotes in addition to double quotes. If None is
                                        set, it uses the default value, ``true``.
        :param allowNumericLeadingZero: allows leading zeros in numbers (e.g. 00012). If None is
                                        set, it uses the default value, ``false``.
        :param allowBackslashEscapingAnyCharacter: allows accepting quoting of all character
                                                   using backslash quoting mechanism. If None is
                                                   set, it uses the default value, ``false``.
        :param mode: allows a mode for dealing with corrupt records during parsing. If None is
                     set, it uses the default value, ``PERMISSIVE``.

                *  ``PERMISSIVE`` : sets other fields to ``null`` when it meets a corrupted \
                  record and puts the malformed string into a new field configured by \
                 ``columnNameOfCorruptRecord``. When a schema is set by user, it sets \
                 ``null`` for extra fields.
                *  ``DROPMALFORMED`` : ignores the whole corrupted records.
                *  ``FAILFAST`` : throws an exception when it meets corrupted records.

        :param columnNameOfCorruptRecord: allows renaming the new field having malformed string
                                          created by ``PERMISSIVE`` mode. This overrides
                                          ``spark.sql.columnNameOfCorruptRecord``. If None is set,
                                          it uses the value specified in
                                          ``spark.sql.columnNameOfCorruptRecord``.
        :param dateFormat: sets the string that indicates a date format. Custom date formats
                           follow the formats at ``java.text.SimpleDateFormat``. This
                           applies to date type. If None is set, it uses the
                           default value value, ``yyyy-MM-dd``.
        :param timestampFormat: sets the string that indicates a timestamp format. Custom date
                                formats follow the formats at ``java.text.SimpleDateFormat``.
                                This applies to timestamp type. If None is set, it uses the
                                default value value, ``yyyy-MM-dd'T'HH:mm:ss.SSSZZ``.

        >>> json_sdf = spark.readStream.json(tempfile.mkdtemp(), schema = sdf_schema)
        >>> json_sdf.isStreaming
        True
        >>> json_sdf.schema == sdf_schema
        True
        """
        self._set_opts(
            schema=schema, primitivesAsString=primitivesAsString, prefersDecimal=prefersDecimal,
            allowComments=allowComments, allowUnquotedFieldNames=allowUnquotedFieldNames,
            allowSingleQuotes=allowSingleQuotes, allowNumericLeadingZero=allowNumericLeadingZero,
            allowBackslashEscapingAnyCharacter=allowBackslashEscapingAnyCharacter,
            mode=mode, columnNameOfCorruptRecord=columnNameOfCorruptRecord, dateFormat=dateFormat,
            timestampFormat=timestampFormat)
        if isinstance(path, basestring):
            return self._df(self._jreader.json(path))
        else:
            raise TypeError("path can be only a single string")

    @since(2.0)
    def parquet(self, path):
        """Loads a Parquet file stream, returning the result as a :class:`DataFrame`.

        You can set the following Parquet-specific option(s) for reading Parquet files:
            * ``mergeSchema``: sets whether we should merge schemas collected from all \
                Parquet part-files. This will override ``spark.sql.parquet.mergeSchema``. \
                The default value is specified in ``spark.sql.parquet.mergeSchema``.

        .. note:: Experimental.

        >>> parquet_sdf = spark.readStream.schema(sdf_schema).parquet(tempfile.mkdtemp())
        >>> parquet_sdf.isStreaming
        True
        >>> parquet_sdf.schema == sdf_schema
        True
        """
        if isinstance(path, basestring):
            return self._df(self._jreader.parquet(path))
        else:
            raise TypeError("path can be only a single string")

    @ignore_unicode_prefix
    @since(2.0)
    def text(self, path):
        """
        Loads a text file stream and returns a :class:`DataFrame` whose schema starts with a
        string column named "value", and followed by partitioned columns if there
        are any.

        Each line in the text file is a new row in the resulting DataFrame.

        .. note:: Experimental.

        :param paths: string, or list of strings, for input path(s).

        >>> text_sdf = spark.readStream.text(tempfile.mkdtemp())
        >>> text_sdf.isStreaming
        True
        >>> "value" in str(text_sdf.schema)
        True
        """
        if isinstance(path, basestring):
            return self._df(self._jreader.text(path))
        else:
            raise TypeError("path can be only a single string")

    @since(2.0)
    def csv(self, path, schema=None, sep=None, encoding=None, quote=None, escape=None,
            comment=None, header=None, inferSchema=None, ignoreLeadingWhiteSpace=None,
            ignoreTrailingWhiteSpace=None, nullValue=None, nanValue=None, positiveInf=None,
            negativeInf=None, dateFormat=None, timestampFormat=None, maxColumns=None,
            maxCharsPerColumn=None, maxMalformedLogPerPartition=None, mode=None):
        """Loads a CSV file stream and returns the result as a  :class:`DataFrame`.

        This function will go through the input once to determine the input schema if
        ``inferSchema`` is enabled. To avoid going through the entire data once, disable
        ``inferSchema`` option or specify the schema explicitly using ``schema``.

        .. note:: Experimental.

        :param path: string, or list of strings, for input path(s).
        :param schema: an optional :class:`pyspark.sql.types.StructType` for the input schema.
        :param sep: sets the single character as a separator for each field and value.
                    If None is set, it uses the default value, ``,``.
        :param encoding: decodes the CSV files by the given encoding type. If None is set,
                         it uses the default value, ``UTF-8``.
        :param quote: sets the single character used for escaping quoted values where the
                      separator can be part of the value. If None is set, it uses the default
                      value, ``"``. If you would like to turn off quotations, you need to set an
                      empty string.
        :param escape: sets the single character used for escaping quotes inside an already
                       quoted value. If None is set, it uses the default value, ``\``.
        :param comment: sets the single character used for skipping lines beginning with this
                        character. By default (None), it is disabled.
        :param header: uses the first line as names of columns. If None is set, it uses the
                       default value, ``false``.
        :param inferSchema: infers the input schema automatically from data. It requires one extra
                       pass over the data. If None is set, it uses the default value, ``false``.
        :param ignoreLeadingWhiteSpace: defines whether or not leading whitespaces from values
                                        being read should be skipped. If None is set, it uses
                                        the default value, ``false``.
        :param ignoreTrailingWhiteSpace: defines whether or not trailing whitespaces from values
                                         being read should be skipped. If None is set, it uses
                                         the default value, ``false``.
        :param nullValue: sets the string representation of a null value. If None is set, it uses
                          the default value, empty string. Since 2.0.1, this ``nullValue`` param
                          applies to all supported types including the string type.
        :param nanValue: sets the string representation of a non-number value. If None is set, it
                         uses the default value, ``NaN``.
        :param positiveInf: sets the string representation of a positive infinity value. If None
                            is set, it uses the default value, ``Inf``.
        :param negativeInf: sets the string representation of a negative infinity value. If None
                            is set, it uses the default value, ``Inf``.
        :param dateFormat: sets the string that indicates a date format. Custom date formats
                           follow the formats at ``java.text.SimpleDateFormat``. This
                           applies to date type. If None is set, it uses the
                           default value value, ``yyyy-MM-dd``.
        :param timestampFormat: sets the string that indicates a timestamp format. Custom date
                                formats follow the formats at ``java.text.SimpleDateFormat``.
                                This applies to timestamp type. If None is set, it uses the
                                default value value, ``yyyy-MM-dd'T'HH:mm:ss.SSSZZ``.
        :param maxColumns: defines a hard limit of how many columns a record can have. If None is
                           set, it uses the default value, ``20480``.
        :param maxCharsPerColumn: defines the maximum number of characters allowed for any given
                                  value being read. If None is set, it uses the default value,
                                  ``-1`` meaning unlimited length.
        :param mode: allows a mode for dealing with corrupt records during parsing. If None is
                     set, it uses the default value, ``PERMISSIVE``.

                * ``PERMISSIVE`` : sets other fields to ``null`` when it meets a corrupted record.
                    When a schema is set by user, it sets ``null`` for extra fields.
                * ``DROPMALFORMED`` : ignores the whole corrupted records.
                * ``FAILFAST`` : throws an exception when it meets corrupted records.

        >>> csv_sdf = spark.readStream.csv(tempfile.mkdtemp(), schema = sdf_schema)
        >>> csv_sdf.isStreaming
        True
        >>> csv_sdf.schema == sdf_schema
        True
        """
        self._set_opts(
            schema=schema, sep=sep, encoding=encoding, quote=quote, escape=escape, comment=comment,
            header=header, inferSchema=inferSchema, ignoreLeadingWhiteSpace=ignoreLeadingWhiteSpace,
            ignoreTrailingWhiteSpace=ignoreTrailingWhiteSpace, nullValue=nullValue,
            nanValue=nanValue, positiveInf=positiveInf, negativeInf=negativeInf,
            dateFormat=dateFormat, timestampFormat=timestampFormat, maxColumns=maxColumns,
            maxCharsPerColumn=maxCharsPerColumn,
            maxMalformedLogPerPartition=maxMalformedLogPerPartition, mode=mode)
        if isinstance(path, basestring):
            return self._df(self._jreader.csv(path))
        else:
            raise TypeError("path can be only a single string")


class DataStreamWriter(object):
    """
    Interface used to write a streaming :class:`DataFrame` to external storage systems
    (e.g. file systems, key-value stores, etc). Use :func:`DataFrame.writeStream`
    to access this.

    .. note:: Experimental.

    .. versionadded:: 2.0
    """

    def __init__(self, df):
        self._df = df
        self._spark = df.sql_ctx
        self._jwrite = df._jdf.writeStream()

    def _sq(self, jsq):
        from pyspark.sql.streaming import StreamingQuery
        return StreamingQuery(jsq)

    @since(2.0)
    def outputMode(self, outputMode):
        """Specifies how data of a streaming DataFrame/Dataset is written to a streaming sink.

        Options include:

        * `append`:Only the new rows in the streaming DataFrame/Dataset will be written to
           the sink
        * `complete`:All the rows in the streaming DataFrame/Dataset will be written to the sink
           every time these is some updates

       .. note:: Experimental.

        >>> writer = sdf.writeStream.outputMode('append')
        """
        if not outputMode or type(outputMode) != str or len(outputMode.strip()) == 0:
            raise ValueError('The output mode must be a non-empty string. Got: %s' % outputMode)
        self._jwrite = self._jwrite.outputMode(outputMode)
        return self

    @since(2.0)
    def format(self, source):
        """Specifies the underlying output data source.

        .. note:: Experimental.

        :param source: string, name of the data source, which for now can be 'parquet'.

        >>> writer = sdf.writeStream.format('json')
        """
        self._jwrite = self._jwrite.format(source)
        return self

    @since(2.0)
    def option(self, key, value):
        """Adds an output option for the underlying data source.

        .. note:: Experimental.
        """
        self._jwrite = self._jwrite.option(key, to_str(value))
        return self

    @since(2.0)
    def options(self, **options):
        """Adds output options for the underlying data source.

       .. note:: Experimental.
        """
        for k in options:
            self._jwrite = self._jwrite.option(k, to_str(options[k]))
        return self

    @since(2.0)
    def partitionBy(self, *cols):
        """Partitions the output by the given columns on the file system.

        If specified, the output is laid out on the file system similar
        to Hive's partitioning scheme.

        .. note:: Experimental.

        :param cols: name of columns

        """
        if len(cols) == 1 and isinstance(cols[0], (list, tuple)):
            cols = cols[0]
        self._jwrite = self._jwrite.partitionBy(_to_seq(self._spark._sc, cols))
        return self

    @since(2.0)
    def queryName(self, queryName):
        """Specifies the name of the :class:`StreamingQuery` that can be started with
        :func:`start`. This name must be unique among all the currently active queries
        in the associated SparkSession.

        .. note:: Experimental.

        :param queryName: unique name for the query

        >>> writer = sdf.writeStream.queryName('streaming_query')
        """
        if not queryName or type(queryName) != str or len(queryName.strip()) == 0:
            raise ValueError('The queryName must be a non-empty string. Got: %s' % queryName)
        self._jwrite = self._jwrite.queryName(queryName)
        return self

    @keyword_only
    @since(2.0)
    def trigger(self, processingTime=None):
        """Set the trigger for the stream query. If this is not set it will run the query as fast
        as possible, which is equivalent to setting the trigger to ``processingTime='0 seconds'``.

        .. note:: Experimental.

        :param processingTime: a processing time interval as a string, e.g. '5 seconds', '1 minute'.

        >>> # trigger the query for execution every 5 seconds
        >>> writer = sdf.writeStream.trigger(processingTime='5 seconds')
        """
        from pyspark.sql.streaming import ProcessingTime
        trigger = None
        if processingTime is not None:
            if type(processingTime) != str or len(processingTime.strip()) == 0:
                raise ValueError('The processing time must be a non empty string. Got: %s' %
                                 processingTime)
            trigger = ProcessingTime(processingTime)
        if trigger is None:
            raise ValueError('A trigger was not provided. Supported triggers: processingTime.')
        self._jwrite = self._jwrite.trigger(trigger._to_java_trigger(self._spark))
        return self

    @ignore_unicode_prefix
    @since(2.0)
    def start(self, path=None, format=None, partitionBy=None, queryName=None, **options):
        """Streams the contents of the :class:`DataFrame` to a data source.

        The data source is specified by the ``format`` and a set of ``options``.
        If ``format`` is not specified, the default data source configured by
        ``spark.sql.sources.default`` will be used.

        .. note:: Experimental.

        :param path: the path in a Hadoop supported file system
        :param format: the format used to save

            * ``append``: Append contents of this :class:`DataFrame` to existing data.
            * ``overwrite``: Overwrite existing data.
            * ``ignore``: Silently ignore this operation if data already exists.
            * ``error`` (default case): Throw an exception if data already exists.
        :param partitionBy: names of partitioning columns
        :param queryName: unique name for the query
        :param options: All other string options. You may want to provide a `checkpointLocation`
            for most streams, however it is not required for a `memory` stream.

        >>> sq = sdf.writeStream.format('memory').queryName('this_query').start()
        >>> sq.isActive
        True
        >>> sq.name
        u'this_query'
        >>> sq.stop()
        >>> sq.isActive
        False
        >>> sq = sdf.writeStream.trigger(processingTime='5 seconds').start(
        ...     queryName='that_query', format='memory')
        >>> sq.name
        u'that_query'
        >>> sq.isActive
        True
        >>> sq.stop()
        """
        self.options(**options)
        if partitionBy is not None:
            self.partitionBy(partitionBy)
        if format is not None:
            self.format(format)
        if queryName is not None:
            self.queryName(queryName)
        if path is None:
            return self._sq(self._jwrite.start())
        else:
            return self._sq(self._jwrite.start(path))


def _test():
    import doctest
    import os
    import tempfile
    from pyspark.sql import Row, SparkSession, SQLContext
    import pyspark.sql.streaming

    os.chdir(os.environ["SPARK_HOME"])

    globs = pyspark.sql.streaming.__dict__.copy()
    try:
        spark = SparkSession.builder.getOrCreate()
    except py4j.protocol.Py4JError:
        spark = SparkSession(sc)

    globs['tempfile'] = tempfile
    globs['os'] = os
    globs['spark'] = spark
    globs['sqlContext'] = SQLContext.getOrCreate(spark.sparkContext)
    globs['sdf'] = \
        spark.readStream.format('text').load('python/test_support/sql/streaming')
    globs['sdf_schema'] = StructType([StructField("data", StringType(), False)])
    globs['df'] = \
        globs['spark'].readStream.format('text').load('python/test_support/sql/streaming')

    (failure_count, test_count) = doctest.testmod(
        pyspark.sql.streaming, globs=globs,
        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE | doctest.REPORT_NDIFF)
    globs['spark'].stop()

    if failure_count:
        exit(-1)


if __name__ == "__main__":
    _test()
