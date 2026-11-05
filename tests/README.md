# Installer regression tests

From the project root, after installing the dependencies in `requirements.txt`:

```powershell
python -B -m unittest discover -s tests -v
```

The tests use the real PySide6 event queue and QThread, with the Qt offscreen
platform. Files are created in temporary directories and removed after each test.
The logger is replaced to avoid writing to the user's profile. External commands,
installer launches and SQL connections are blocked unless a test supplies a mock.

Coverage includes failed-stage retry, verification failure, cancellation and window
shutdown, SQL 2014 selection, missing/corrupt package inputs, shared files, update
failure propagation, stale extraction directories, preservation of existing
customer databases, and partial prerequisite installation failures.

These tests do not perform a real SQL Server or MSI installation. The generated
EXE and SFX packages must be rebuilt separately to include source changes.
