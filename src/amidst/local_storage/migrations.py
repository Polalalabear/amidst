"""Versioned PostgreSQL schema; canonical evidence and history are append-only."""

# Keep SQL bytes stable after application: these strings are migration fingerprints.
# ruff: noqa: E501

BASE = """
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE runs(run_ref TEXT PRIMARY KEY, scope_json TEXT NOT NULL,
 receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL);
CREATE TABLE records(run_ref TEXT NOT NULL REFERENCES runs(run_ref),kind TEXT NOT NULL,
 record_ref TEXT NOT NULL,start_time DOUBLE PRECISION NOT NULL,end_time DOUBLE PRECISION NOT NULL,
 record_json TEXT NOT NULL,envelope_sha256 TEXT NOT NULL,PRIMARY KEY(run_ref,kind,record_ref));
CREATE INDEX records_interval ON records(run_ref,kind,start_time,end_time,record_ref);
CREATE TABLE record_cameras(run_ref TEXT NOT NULL,kind TEXT NOT NULL,record_ref TEXT NOT NULL,
 camera_id TEXT NOT NULL,start_time DOUBLE PRECISION NOT NULL,end_time DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(run_ref,kind,record_ref,camera_id),
 FOREIGN KEY(run_ref,kind,record_ref) REFERENCES records(run_ref,kind,record_ref));
CREATE INDEX cameras_interval ON record_cameras(run_ref,camera_id,kind,start_time,end_time,record_ref);
CREATE TABLE record_regions(run_ref TEXT NOT NULL,kind TEXT NOT NULL,record_ref TEXT NOT NULL,
 region_id TEXT NOT NULL,start_time DOUBLE PRECISION NOT NULL,end_time DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(run_ref,kind,record_ref,region_id),
 FOREIGN KEY(run_ref,kind,record_ref) REFERENCES records(run_ref,kind,record_ref));
CREATE INDEX regions_interval ON record_regions(run_ref,region_id,kind,start_time,end_time,record_ref);
CREATE TABLE revisions(run_ref TEXT NOT NULL REFERENCES runs(run_ref),kind TEXT NOT NULL,
 entity_ref TEXT NOT NULL,version INTEGER NOT NULL,revision_json TEXT NOT NULL,
 revision_sha256 TEXT NOT NULL,PRIMARY KEY(run_ref,kind,entity_ref,version));
CREATE FUNCTION deny_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN RAISE EXCEPTION 'APPEND_ONLY_RECORD'; END $$;
"""

EXTENSIONS = """
CREATE TABLE jobs(run_ref TEXT NOT NULL REFERENCES runs(run_ref),job_ref TEXT NOT NULL,
 version INTEGER NOT NULL,previous_sha256 TEXT,payload_json TEXT NOT NULL,
 revision_sha256 TEXT NOT NULL,PRIMARY KEY(run_ref,job_ref,version));
CREATE TABLE descriptor_indexes(run_ref TEXT NOT NULL REFERENCES runs(run_ref),index_ref TEXT NOT NULL,
 bundle_json TEXT NOT NULL,bundle_sha256 TEXT NOT NULL,PRIMARY KEY(run_ref,index_ref));
CREATE TABLE index_heads(run_ref TEXT PRIMARY KEY REFERENCES runs(run_ref),index_ref TEXT NOT NULL,
 version INTEGER NOT NULL,FOREIGN KEY(run_ref,index_ref) REFERENCES descriptor_indexes(run_ref,index_ref));
CREATE TABLE media_bindings(run_ref TEXT NOT NULL REFERENCES runs(run_ref),media_ref TEXT NOT NULL,
 payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,PRIMARY KEY(run_ref,media_ref));
CREATE TABLE topologies(run_ref TEXT NOT NULL REFERENCES runs(run_ref),topology_sha256 TEXT NOT NULL,
 payload_json TEXT NOT NULL,PRIMARY KEY(run_ref,topology_sha256));
CREATE TABLE topology_heads(run_ref TEXT PRIMARY KEY REFERENCES runs(run_ref),topology_sha256 TEXT NOT NULL,
 version INTEGER NOT NULL,FOREIGN KEY(run_ref,topology_sha256) REFERENCES topologies(run_ref,topology_sha256));
CREATE TABLE topology_cache(run_ref TEXT NOT NULL,topology_sha256 TEXT NOT NULL,query_sha256 TEXT NOT NULL,
 payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,
 PRIMARY KEY(run_ref,topology_sha256,query_sha256),
 FOREIGN KEY(run_ref,topology_sha256) REFERENCES topologies(run_ref,topology_sha256));
"""

MIGRATIONS = ((1, BASE), (2, EXTENSIONS))
IMMUTABLE = (
    "runs",
    "records",
    "record_cameras",
    "record_regions",
    "revisions",
    "jobs",
    "descriptor_indexes",
    "media_bindings",
    "topologies",
    "topology_cache",
)
