-- Runs once, when the db volume is first created. pytest uses this separate database so
-- tests never touch your local data.
CREATE DATABASE proxylog_test;
