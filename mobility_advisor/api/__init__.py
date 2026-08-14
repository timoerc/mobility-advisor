"""FastAPI application, split by concern: schemas (request bodies), deps (shared
process-lifetime state), routes/ (one router per resource area), and recommendation/
(the post-processing pipeline that turns raw pipeline/optimizer output into the wire-
contract Recommendation)."""
