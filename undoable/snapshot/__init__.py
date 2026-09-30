# git_snapshot.py: git-based file snapshot + rollback. Respects .gitignore --
# ignored files are never captured or touched. DB dumps and lockfile
# snapshots are a separate, later task ("Undo for databases and lockfiles").
