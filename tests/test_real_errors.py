"""Kiểm thử dựng từ các lỗi gặp trong lần chạy thật (268 danh thiếp).

Tên người, số điện thoại, email đã được thay bằng dữ liệu giả nhưng giữ nguyên KIỂU lỗi OCR.
"""

from app.engine.parser import canonical_phone, format_phone, parse_card


def test_plus_sign_read_as_digit():
    # "+84" có ký tự rác phía trước ("+" hoặc biểu tượng điện thoại bị đọc thành số)
    assert format_phone("484912345678") == "0912 345 678"
    assert format_phone("884912345678") == "0912 345 678"
    assert format_phone("4840912345678") == "0912 345 678"
    assert format_phone("0884912345678") == "0912 345 678"
    assert format_phone("7842838123456") == "028 3812 3456"
    assert format_phone("8402838123456") == "028 3812 3456"  # +84 (0)28 ...
    assert format_phone("0002838123456") == "028 3812 3456"
    assert format_phone("912345678") == "0912 345 678"
    # Số nước ngoài, có 1 ký tự rác đầu
    assert canonical_phone("76566611212") == "+6566611212"
    assert canonical_phone("+48 723 972 779") == "+48723972779"
    # Tổng đài giữ nguyên
    assert canonical_phone("1800 282 218") == "1800282218"


def test_two_mobiles_glued_together():
    r = parse_card(["Tran Van Hoc", "M: 09123456780987654321"])
    assert r["mobile"] == "0912 345 678"
    assert "0987 654 321" in (r["phone"] + r["note"])


def test_missing_dot_after_www():
    assert parse_card(["Lam Van Tri", "wwwtico-sg.vn"])["website"] == "www.tico-sg.vn"
    assert parse_card(["Lam Van Tri", "wwwwhitchins.com"])["website"] == "www.hitchins.com"
    assert parse_card(["Lam Van Tri", "0wwwbestmix.vn"])["website"] == "www.bestmix.vn"


def test_email_with_lost_at_sign():
    r = parse_card(["Tran Van An", "Sales Manager", "NS BlueScope Lysaght Vietnam Limited",
                    "an.tranobluescope.com", "028 3812 0100"])
    assert r["email"] == "an.tran@bluescope.com"
    assert r["website"] == ""
    # hộp thư gmail, "@" đọc thành "o"/"0"
    assert parse_card(["Le Nhu Hoa", "hoa.le1979ogmail.com"])["email"] == "hoa.le1979@gmail.com"
    assert parse_card(["Le Nhu Hoa", "hoa.le19790gmail.com"])["email"] == "hoa.le1979@gmail.com"
    # "@" bị mất hẳn; "mateco" là một từ trên thẻ
    r = parse_card(["Nguyen Chi Bao", "Sales Director", "MATECO", "baonc.matecogmail.com"])
    assert r["email"] == "baonc.mateco@gmail.com"
    # không có bằng chứng thì không đoán bừa
    assert parse_card(["Le Van Ba", "abc.defghijk.com"])["email"] == ""


def test_email_domain_with_extra_letter():
    r = parse_card(["Pham Van Nam", "Công ty TNHH Hilti Việt Nam", "E: nam.pham@dhilti.com"])
    assert r["email"] == "nam.pham@hilti.com"
    r = parse_card(["Tran Van An", "NS BlueScope Vietnam", "an.tran@obluescope.com", "www.bluescope.com"])
    assert r["email"] == "an.tran@bluescope.com"


def test_no_fake_emails_from_website_line():
    r = parse_card(["Nguyen Van Hoan", "Director", "BAO QUAN CO., JSC", "Web: www.baoquan.com.vn"])
    assert r["email"] == "" and r["website"] == "www.baoquan.com.vn"
    assert parse_card(["Tran Thi Phuong", "Email: a@daeyeong.vn"])["email"] == ""


def test_company_not_taken_from_url_or_slogan():
    r = parse_card(["Le Van Tam", "Project Sales", "www.linkedin.com/company/amscont", "AMS CONSTRUCTION COMPANY LIMITED"])
    assert r["company"] == "AMS CONSTRUCTION COMPANY LIMITED"
    r = parse_card(["Tran Van Hai", "Market Development Manager", "Tremco CPG Malaysia Sdn. Bhd.",
                    "(An RPM Platform APAC Company)"])
    assert r["company"].startswith("Tremco")
    r = parse_card(["BIBICA CORPORATION", "A Member Of The Pan Group", "Vo Quoc Kha", "Director"])
    assert r["company"] == "BIBICA CORPORATION"
    r = parse_card(["Kiều Văn Lâm", "Giám đốc Chi nhánh TONMAT Bắc Ninh", "Công ty CP Tôn Mát"])
    assert r["company"] == "Công ty CP Tôn Mát"


def test_names():
    # biệt danh trong ngoặc
    assert parse_card(["LANGS", "VO DINH QUOC (BEAN)", "Sales Director"])["name"] == "Vo Dinh Quoc"
    assert parse_card(["Nguyen Thi Hoai Thu (Autumn)", "Country Manager"])["name"] == "Nguyen Thi Hoai Thu"
    # chức vụ / bộ phận không phải tên người
    r = parse_card(["Business Development", "Manager Heavy-duty fixings", "RAWLPLUG", "Marcin Nowak"])
    assert r["name"] == "Marcin Nowak"
    r = parse_card(["Engineered Building Solutions", "PMD Manager", "Pebsteel", "Le Van Minh"])
    assert r["name"] == "Le Van Minh"
    # danh xưng / học vị đứng trước tên
    assert parse_card(["Ths. Võ Nguyên Dũng", "Giám Đốc"])["name"] == "Võ Nguyên Dũng"
    assert parse_card(["Eng. Pham Cong Tien", "CONSTRUCTION SERVICE TRADING COMPANY"])["name"] == "Pham Cong Tien"
    # tên và chức vụ chung một dòng
    r = parse_card(["KS. HUỲNH LÊ TÂN / Quản lý dự án", "Công ty Cổ Phần Tư vấn Xây dựng"])
    assert r["name"] == "Huỳnh Lê Tân" and r["title"] == "Quản lý dự án"
    # một chữ rác đứng trước họ
    assert parse_card(["ONEO Ngô Hoàng Hải", "phucmygia.vn"])["name"] == "Ngô Hoàng Hải"
    # trùng tên công ty thì không phải tên người
    r = parse_card(["Quang Phong", "CÔNG TY TNHH TM DV XÂY DỰNG QUANG PHONG", "Phạm Công Thắng", "Phó Giám đốc"])
    assert r["name"] == "Phạm Công Thắng"


def test_classification_on_real_brands():
    from app.engine.classify import classify, load_categories

    cats = load_categories()

    def cat(company, title="", email="", website="", raw=""):
        card = {"company": company, "title": title, "email": email, "website": website}
        return classify(card, raw or company + "\n" + title, cats)

    assert cat("Công ty TNHH Hilti Việt Nam", "Kỹ sư công trường", "a.b@hilti.com") == "Nhà cung cấp vật tư / thiết bị"
    assert cat("NS BlueScope Lysaght Vietnam Limited", "Sales Manager") == "Nhà cung cấp vật tư / thiết bị"
    assert cat("KNAUF", "Specification Manager", website="www.knaufapac.com") == "Nhà cung cấp vật tư / thiết bị"
    assert cat("CÔNG TY TNHH MITSUBISHI ESTATE VIỆT NAM", "Giám Đốc Đầu Tư") == "Chủ đầu tư / Bất động sản"
    assert cat("TAKENAKA VIETNAM CO., LTD.", "General Director") == "Nhà thầu xây dựng"
    assert cat("JLL VIETNAM", "Project Manager") == "Tư vấn thiết kế / giám sát / QS"
    # "Business Development Manager" của nhà cung cấp không còn bị xếp vào Chủ đầu tư
    assert cat("RAWLPLUG", "Business Development Manager", website="www.rawlplug.com") == "Nhà cung cấp vật tư / thiết bị"


def test_user_category_file_is_upgraded(tmp_path):
    import json

    from app.engine.classify import sync_user_categories

    f = tmp_path / "phan-loai.json"
    f.write_text(json.dumps({"version": 1, "categories": [
        {"name": "Chủ đầu tư / Bất động sản", "keywords": ["development", "khách quen của tôi"]},
        {"name": "Nhóm riêng của tôi", "keywords": ["abc"]},
        {"name": "Khác", "keywords": []},
    ]}, ensure_ascii=False), encoding="utf-8")
    assert sync_user_categories(f)
    data = json.loads(f.read_text(encoding="utf-8"))
    names = [c["name"] for c in data["categories"]]
    assert names[-1] == "Khác" and "Nhóm riêng của tôi" in names and "Nhà thầu xây dựng" in names
    owner = data["categories"][0]["keywords"]
    assert "khách quen của tôi" in owner and "development" not in owner and "estate" in owner
    assert not sync_user_categories(f)  # lần sau không cập nhật lại


def test_classify_glued_company_name():
    from app.engine.classify import classify, load_categories

    card = {"company": "CÔNG TY TNHH MITSUBISHIESTATE VIỆTNAM", "title": "Phó Giám Đốc", "email": "", "website": ""}
    # chỉ áp dụng khi cả tên viết liền một khối
    card2 = {"company": "MITSUBISHIESTATE", "title": "", "email": "", "website": ""}
    assert classify(card2, "", load_categories()) == "Chủ đầu tư / Bất động sản"
    assert classify(card, "", load_categories()) == "Chủ đầu tư / Bất động sản"
