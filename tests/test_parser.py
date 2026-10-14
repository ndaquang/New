from app.engine.parser import format_phone, parse_card

# Các dòng chữ như bộ OCR trả về (theo thứ tự đọc, đoạn cách xa trên cùng hàng tách riêng).
VITECCONS = [
    {"text": "VITECCONS", "height": 30},
    {"text": "NGUYEN DANG QUANG", "height": 26},
    {"text": "BUILD BY HEART", "height": 10},
    {"text": "Head of Tender Department", "height": 20},
    {"text": "0795 688 399", "height": 18},
    {"text": "@ quang.nguyen@viteccons.vn", "height": 18},
    {"text": "HCM:109 Hoang Hoa Tham, Gia", "height": 18},
    {"text": "Dinh Ward, Ho Chi Minh City,", "height": 18},
    {"text": "Vietnam.", "height": 18},
    {"text": "HN:", "height": 18},
    {"text": "No. 4NVC1, Lot 4, The Manor", "height": 18},
    {"text": "Central Park, Dinh Cong Ward,", "height": 18},
    {"text": "Ha Noi City, Vietnam.", "height": 18},
    {"text": "www.viteccons.vn", "height": 16},
    {"text": "MST: 0309553779", "height": 16},
]

CESCO = [
    {"text": "Vũ Anh Kim Long", "height": 30},
    {"text": "Trưởng bộ phận bán hàng kỹ thuật End user", "height": 22},
    {"text": "CESCO", "height": 60},
    {"text": "Service sales manager-IEM", "height": 22},
    {"text": "Your trustworthy partner", "height": 18},
    {"text": "Hp: (+84) 918 196 121", "height": 22},
    {"text": "Email: long.vu@cesco.com.vn", "height": 22},
    {"text": "Công Ty TNHH CESCO", "height": 26},
    {"text": "CESCO Co., Ltd", "height": 26},
    {"text": "Trụ Sở", "height": 18},
    {"text": ": Số 6 Đường số 2, Kp.5", "height": 18},
    {"text": "P.Hiệp Bình Phước, TP.Thủ Đức, Tp.HCM", "height": 18},
    {"text": "Headquater", "height": 18},
    {"text": ": 6 Street 2, Quarter 5", "height": 18},
    {"text": "H.B.Phuoc Ward, Thu Duc City, HCM City", "height": 18},
    {"text": "ĐT/Fax", "height": 18},
    {"text": ": +84 28 3727 3079", "height": 18},
    {"text": "www.cesco.com.vn", "height": 20},
    {"text": "MST", "height": 18},
    {"text": ": 0312 522 851", "height": 18},
]


def test_viteccons_card():
    r = parse_card(VITECCONS)
    assert r["name"] == "Nguyen Dang Quang"
    assert r["title"] == "Head of Tender Department"
    assert r["company"] == "VITECCONS"  # suy ra từ tên miền email/website
    assert r["mobile"] == "0795 688 399"
    assert r["phone"] == "" and r["note"] == ""  # MST không bị nhầm là số điện thoại
    assert r["email"] == "quang.nguyen@viteccons.vn"
    assert r["website"] == "www.viteccons.vn"
    assert r["address"] == "HCM:109 Hoang Hoa Tham, Gia, Dinh Ward, Ho Chi Minh City, Vietnam."
    assert r["address2"] == "HN: No. 4NVC1, Lot 4, The Manor, Central Park, Dinh Cong Ward, Ha Noi City, Vietnam."


def test_cesco_card():
    r = parse_card(CESCO)
    assert r["name"] == "Vũ Anh Kim Long"
    assert r["title"] == "Trưởng bộ phận bán hàng kỹ thuật End user / Service sales manager-IEM"
    assert r["company"] == "Công Ty TNHH CESCO"
    assert r["mobile"] == "0918 196 121"
    assert r["phone"] == "028 3727 3079"
    assert r["fax"] == "028 3727 3079"
    assert r["email"] == "long.vu@cesco.com.vn"
    assert r["website"] == "www.cesco.com.vn"
    assert r["address"] == "Trụ Sở: Số 6 Đường số 2, Kp.5, P.Hiệp Bình Phước, TP.Thủ Đức, Tp.HCM"
    assert r["address2"].startswith("Headquater: 6 Street 2")
    assert "0312" not in r["note"]


def test_vietnamese_card():
    r = parse_card([
        {"text": "CÔNG TY TNHH XÂY DỰNG ABC", "height": 30},
        {"text": "NGUYỄN VĂN AN", "height": 42},
        {"text": "Giám đốc Dự án", "height": 20},
        {"text": "Mobile: 0903 123 456", "height": 18},
        {"text": "Tel: (028) 3823 4567 - Fax: 028 3823 4568", "height": 18},
        {"text": "Email: an.nguyen @ abc.com.vn", "height": 18},
        {"text": "Địa chỉ: 123 Nguyễn Huệ, Phường Bến Nghé,", "height": 18},
        {"text": "Quận 1, TP. Hồ Chí Minh", "height": 18},
    ])
    assert r["company"] == "CÔNG TY TNHH XÂY DỰNG ABC"
    assert r["name"] == "Nguyễn Văn An"
    assert r["title"] == "Giám đốc Dự án"
    assert (r["mobile"], r["phone"], r["fax"]) == ("0903 123 456", "028 3823 4567", "028 3823 4568")
    assert r["email"] == "an.nguyen@abc.com.vn"
    assert r["address"] == "123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh"


def test_two_numbers_one_line():
    r = parse_card(["Lê Minh Tuấn", "HP: 0903 111 222 / 0988 333 444", "Mã số thuế: 0101234567"])
    assert (r["mobile"], r["phone"], r["note"]) == ("0903 111 222", "0988 333 444", "")


def test_format_phone():
    assert format_phone("0903123456") == "0903 123 456"
    assert format_phone("+84 28 3823 4567") == "028 3823 4567"


def test_classify():
    from app.engine.classify import classify, load_categories

    cats = load_categories()
    vit = parse_card(VITECCONS)
    assert classify(vit, "\n".join(l["text"] for l in VITECCONS), cats) == "Nhà thầu xây dựng"
    # "của", "Sơn", "Đà Nẵng" không được khớp nhầm từ khóa vật tư ("cửa", "sơn", "đá")
    other = {"company": "Văn phòng của anh Sơn", "title": "", "email": "", "website": ""}
    assert classify(other, "Đà Nẵng", cats) == "Khác"


# Chữ do VietOCR thật đọc ra trên Windows (ảnh mẫu): "@" bị đọc thành D / O / o.
def _lines(raw: str):
    return [{"text": t.strip(), "height": 0} for t in raw.split("|")]


def test_vietocr_mangled_at_sign():
    r = parse_card(_lines(
        "NGUYEN DANG QUANG | VITECCONS | Head of Tender Department | BUILD BY HEART | 0795 688 399 | "
        "quang.nguyen Dviteccons.vn | HCM: 109 Hoang Hoa Tham, Gia | Dinh Ward, Ho Chi Minh City | Vietnam. | "
        "HN: No. 4NVC1, Lot 4, The Manor | Central Park, Dinh Cong Ward, | Ha Noi City, Vietnam | www.viteccons.vn | MST:00005537799"
    ))
    assert r["email"] == "quang.nguyen@viteccons.vn"
    assert r["website"] == "www.viteccons.vn"
    assert r["company"] == "VITECCONS"
    assert r["name"] == "Nguyen Dang Quang"
    assert r["mobile"] == "0795 688 399" and r["phone"] == ""

    r = parse_card(_lines(
        "Vũ Anh Kim Long | CESCO | Trưởng bộ phận bán hàng kỹ thuật End user | Service sales manageriem | "
        "Your trustworthy partner | Hp: (+84) 918 196 121 | Email: long.vuocesco..com.vn | Công Ty TNHH CESCO | "
        "CESCO CO., Ltd | Trụ Sở | Số 6 Đường số 2, Kp.5 | P.Hiệp Bình Phước, TP. Thủ Đức, Tp.HCM | ĐT/Fax | "
        "+84 28 3727 3079 | www.cesco.com.vn | MST | 0312522881"
    ))
    assert r["email"] == "long.vu@cesco.com.vn"
    assert r["website"] == "www.cesco.com.vn"
    assert r["name"] == "Vũ Anh Kim Long"
    assert r["company"] == "Công Ty TNHH CESCO"
    assert r["mobile"] == "0918 196 121"
    assert r["phone"] == r["fax"] == "028 3727 3079"
    assert "0312" not in r["note"]

    r = parse_card(_lines("NGUYEN DANG QUANG | 0795 688 399 | quang.nguyen Quiteccons.vn | www.viteccons.vn"))
    assert r["email"] == "quang.nguyen@viteccons.vn"

    r = parse_card(_lines("Lê Văn Bình | Email: binh.le Ocesco.com.vn | www.cesco.com.vn"))
    assert r["email"] == "binh.le@cesco.com.vn"
