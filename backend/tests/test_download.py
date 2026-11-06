def test_app_is_not_offered_until_the_file_is_there(client):
    assert client.head("/api/public/rastescan.apk").status_code == 404
    assert client.get("/api/public/rastescan.apk").status_code == 404


def test_app_downloads_as_an_android_package(client, tmp_path):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "downloads" / "rastescan.apk").write_bytes(b"PK-not-really-an-apk")

    head = client.head("/api/public/rastescan.apk")
    assert head.status_code == 200

    got = client.get("/api/public/rastescan.apk")
    assert got.status_code == 200
    assert got.content == b"PK-not-really-an-apk"
    assert got.headers["content-type"] == "application/vnd.android.package-archive"
    assert 'filename="RasteScan.apk"' in got.headers["content-disposition"]
