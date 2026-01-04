from app.db.repository import repo


class TestDB:
    def test_create_repo(self, tmp_path):
        repo_path = tmp_path / 'test_db.db'
        assert(not repo_path.is_file())
        repo.attach(repo_path, False)
        assert(repo_path.is_file())

