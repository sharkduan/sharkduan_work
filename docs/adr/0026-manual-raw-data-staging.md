# Manual Raw Data Staging

The first ETL will not download CovalentInDB, CovPDB, or CovBinderInPDB automatically. Users will manually place source files under `data/raw/`, and ETL code will only read, parse, normalize, and validate staged files. Automatic downloading is deferred because database URLs, access requirements, file layouts, and licensing terms may change independently of the ETL logic.
