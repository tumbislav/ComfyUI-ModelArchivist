# Model Archivist
What do you do when the number of models in your ComfyUI setup becomes unmanageable and your drop-downs extend over the edge of the screen? You off-load those that you're not using to a separate drive, of course. But then you have to keep track of those that you've moved and make sure you always have the set that you need.

This is the tool that lets you keep the chaos under control.

# Config file
The file `config.toml` is typically located in the root folder.

# Assumptions

- ModelArchivist is a single-user application using SQLite.
- If any configured model or workflow folder is inaccessible, the application runs read-only and does not scan files.
- Every configured working directory has exactly one archive counterpart, and neither directory may be reused in another pair.
- A model or workflow has at most one working component set and one archive component set. Missing sides have no component set; their prospective paths are derived from the configured pair.
- A workflow is identified by a UUID in its top-level `id` field. JSON files without a usable UUID are ignored.
- Workflow IDs uniquely identify one relative filename across working and archive storage.
- A model is identified by the SHA-256 hash of its main weights file.
- Normal scans trust a usable cached SHA-256 from Archivist or LoraManager metadata and hash weights only when no usable cached hash exists.
- User-requested rehash scans calculate hashes from every weights file, including archived files on slow storage.
- The risk of stale cached hashes and files changing during a scan is accepted. Users can request a manual rescan or rehash.
- Other applications may rename files in the working set. The working filename is authoritative and metadata can be updated later.
- Invalid third-party metadata is treated like an unreadable sidecar. Third-party and Archivist metadata are not reconciled.
- Orphaned sidecars and orphaned example directories are ignored.
