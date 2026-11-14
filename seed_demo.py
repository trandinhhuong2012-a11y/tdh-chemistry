# -*- coding: utf-8 -*-
"""Dữ liệu minh hoạ (DEMO) cho TĐH Chemistry: 1 lớp, 3 học sinh, 31 câu Hoá 12, 1 đề đang mở.

Chỉ chạy một lần khi cơ sở dữ liệu còn trống. Tất cả đều là dữ liệu giả lập.
"""
import json

G = 12
CH1, CH2, CH3, CH4 = 'Ester – Lipid', 'Carbohydrate', 'Hợp chất chứa nitrogen', 'Polymer'


def sc(chapter, topic, level, stem, right, wrong, pos, expl=''):
    """Trắc nghiệm 4 phương án; `pos` là vị trí (0–3) đặt đáp án đúng."""
    opts = list(wrong)
    opts.insert(pos, right)
    return dict(type='single_choice', chapter=chapter, topic=topic, level=level, stem=stem,
                payload={'choices': [{'id': 'ABCD'[i], 'text': t} for i, t in enumerate(opts)]},
                key={'correct': 'ABCD'[pos]}, expl=expl)


def tf(chapter, topic, level, stem, items, expl=''):
    return dict(type='true_false', chapter=chapter, topic=topic, level=level, stem=stem,
                payload={'statements': [{'id': 'abcd'[i], 'text': t} for i, (t, _) in enumerate(items)]},
                key={'abcd'[i]: v for i, (_, v) in enumerate(items)}, expl=expl)


def sa(chapter, topic, level, stem, value, tol='0', expl=''):
    return dict(type='short_answer', chapter=chapter, topic=topic, level=level, stem=stem, payload={},
                key={'mode': 'number', 'value': value, 'tol': tol}, expl=expl)


QUESTIONS = [
    # ── Ester – Lipid ──
    sc(CH1, 'Ester', 'NB', 'Công thức cấu tạo thu gọn của ethyl acetate là',
       'CH3COOC2H5', ['HCOOC2H5', 'CH3COOCH3', 'C2H5COOCH3'], 1),
    sc(CH1, 'Lipid', 'NB', 'Chất béo là triester của glycerol với',
       'acid béo', ['acid vô cơ', 'amino acid', 'alcohol đơn chức'], 0),
    sc(CH1, 'Ester', 'TH', 'Thuỷ phân hoàn toàn methyl propanoate trong dung dịch NaOH dư, đun nóng, thu được muối có công thức là',
       'C2H5COONa', ['CH3COONa', 'HCOONa', 'C3H7COONa'], 2,
       'C2H5COOCH3 + NaOH -> C2H5COONa + CH3OH.'),
    sc(CH1, 'Lipid', 'TH', 'Xà phòng hoá hoàn toàn tristearin bằng dung dịch NaOH thu được glycerol và muối',
       'C17H35COONa', ['C17H33COONa', 'C15H31COONa', 'C17H31COONa'], 3,
       '(C17H35COO)3C3H5 + 3NaOH -> 3C17H35COONa + C3H5(OH)3.'),
    sc(CH1, 'Ester', 'VD', 'Số ester là đồng phân cấu tạo của nhau, có cùng công thức phân tử C4H8O2, là',
       '4', ['2', '3', '5'], 2,
       'HCOOCH2CH2CH3, HCOOCH(CH3)2, CH3COOC2H5, C2H5COOCH3.'),
    tf(CH1, 'Ester', 'TH', 'Ethyl acetate (CH3COOC2H5) là ester thường được dùng làm dung môi. Xét các phát biểu sau:', [
        ('Ethyl acetate có công thức phân tử C4H8O2.', True),
        ('Ethyl acetate được điều chế từ acetic acid và ethanol (xúc tác H2SO4 đặc, đun nóng).', True),
        ('Phản ứng thuỷ phân ethyl acetate trong môi trường acid là phản ứng một chiều.', False),
        ('Thuỷ phân ethyl acetate trong dung dịch NaOH thu được sodium acetate và ethanol.', True)],
       'Thuỷ phân ester trong môi trường acid là phản ứng thuận nghịch.'),
    sa(CH1, 'Ester', 'VD', 'Xà phòng hoá hoàn toàn 8,8 gam ethyl acetate bằng dung dịch NaOH vừa đủ, thu được m gam muối. '
       'Giá trị của m là bao nhiêu? (Cho H = 1; C = 12; O = 16; Na = 23. Làm tròn đến hàng phần mười.)', '8.2', '0.05',
       'n(ester) = 8,8 : 88 = 0,1 mol -> m(CH3COONa) = 0,1 × 82 = 8,2 gam.'),
    sa(CH1, 'Ester', 'TH', 'Có bao nhiêu ester là đồng phân cấu tạo của nhau ứng với công thức phân tử C3H6O2?', '2', '0',
       'HCOOC2H5 và CH3COOCH3.'),

    # ── Carbohydrate ──
    sc(CH2, 'Glucose – Fructose', 'NB', 'Chất nào sau đây thuộc loại monosaccharide?',
       'Glucose', ['Saccharose', 'Tinh bột', 'Cellulose'], 0),
    sc(CH2, 'Saccharose', 'NB', 'Công thức phân tử của saccharose là',
       'C12H22O11', ['C6H12O6', '(C6H10O5)n', 'C6H14O6'], 1),
    sc(CH2, 'Glucose – Fructose', 'TH', 'Dung dịch chất nào sau đây vừa hoà tan được Cu(OH)2 ở nhiệt độ thường tạo dung dịch '
       'màu xanh lam, vừa có phản ứng với thuốc thử Tollens?',
       'Glucose', ['Saccharose', 'Glycerol', 'Ethanol'], 3),
    sc(CH2, 'Tinh bột – Cellulose', 'TH', 'Thuỷ phân hoàn toàn tinh bột trong môi trường acid thu được',
       'glucose', ['fructose', 'saccharose', 'maltose'], 2),
    sc(CH2, 'Tinh bột – Cellulose', 'VD', 'Thuỷ phân hoàn toàn 16,2 gam tinh bột (hiệu suất 100 %) thu được m gam glucose. '
       'Giá trị của m là', '18,0', ['16,2', '9,0', '36,0'], 1,
       '(C6H10O5)n + nH2O -> nC6H12O6; n(mắt xích) = 16,2 : 162 = 0,1 mol -> m = 0,1 × 180 = 18,0 gam.'),
    tf(CH2, 'Glucose – Fructose', 'TH', 'Xét các phát biểu sau về glucose và fructose:', [
        ('Glucose và fructose là đồng phân của nhau.', True),
        ('Trong môi trường kiềm, fructose có thể chuyển hoá thành glucose.', True),
        ('Glucose làm mất màu nước bromine.', True),
        ('Fructose thuộc loại disaccharide.', False)],
       'Fructose là monosaccharide, cùng công thức phân tử C6H12O6 với glucose.'),
    sa(CH2, 'Glucose – Fructose', 'VD', 'Cho 18 gam glucose tác dụng hoàn toàn với lượng dư thuốc thử Tollens, thu được m gam Ag. '
       'Giá trị của m là bao nhiêu? (Cho H = 1; C = 12; O = 16; Ag = 108. Làm tròn đến hàng phần mười.)', '21.6', '0.05',
       'n(glucose) = 0,1 mol -> n(Ag) = 0,2 mol -> m = 21,6 gam.'),
    sa(CH2, 'Glucose – Fructose', 'NB', 'Phân tử glucose dạng mạch hở có bao nhiêu nhóm hydroxy (–OH)?', '5', '0',
       'CH2OH[CHOH]4CHO có 5 nhóm –OH và 1 nhóm –CHO.'),

    # ── Hợp chất chứa nitrogen ──
    sc(CH3, 'Amine', 'NB', 'Chất nào sau đây là amine bậc hai?',
       'CH3NHCH3', ['CH3NH2', '(CH3)3N', 'C6H5NH2'], 2),
    sc(CH3, 'Amino acid', 'NB', 'Glycine là amino acid đơn giản nhất, có công thức là',
       'H2NCH2COOH', ['CH3CH(NH2)COOH', 'H2NCH2CH2COOH', 'C6H5NH2'], 0),
    sc(CH3, 'Amine', 'TH', 'Dung dịch chất nào sau đây làm quỳ tím hoá xanh?',
       'Methylamine', ['Aniline', 'Glycine', 'Glutamic acid'], 1),
    sc(CH3, 'Peptide – Protein', 'TH', 'Số liên kết peptide trong phân tử tripeptide mạch hở Gly-Ala-Val là',
       '2', ['3', '1', '4'], 3),
    sc(CH3, 'Peptide – Protein', 'TH', 'Peptide nào sau đây có phản ứng màu biuret với Cu(OH)2 trong môi trường kiềm?',
       'Gly-Ala-Gly', ['Gly-Ala', 'Ala-Ala', 'Gly-Gly'], 0,
       'Peptide có từ hai liên kết peptide trở lên (từ tripeptide) mới có phản ứng màu biuret.'),
    sc(CH3, 'Amino acid', 'VD', 'Cho 0,1 mol glycine tác dụng vừa đủ với dung dịch NaOH. Khối lượng muối thu được là '
       '(cho H = 1; C = 12; N = 14; O = 16; Na = 23)',
       '9,7 gam', ['7,5 gam', '11,1 gam', '9,5 gam'], 2,
       'H2NCH2COOH + NaOH -> H2NCH2COONa + H2O; m = 0,1 × 97 = 9,7 gam.'),
    tf(CH3, 'Amine', 'TH', 'Xét các phát biểu sau về aniline (C6H5NH2):', [
        ('Aniline là amine bậc một.', True),
        ('Dung dịch aniline làm quỳ tím hoá xanh.', False),
        ('Aniline tác dụng với nước bromine tạo kết tủa trắng.', True),
        ('Ở điều kiện thường, aniline tan tốt trong nước.', False)],
       'Aniline có tính base rất yếu, không làm đổi màu quỳ tím và ít tan trong nước.'),
    sa(CH3, 'Amine', 'VD', 'Cho 4,5 gam ethylamine tác dụng vừa đủ với dung dịch HCl, thu được m gam muối. '
       'Giá trị của m là bao nhiêu? (Cho H = 1; C = 12; N = 14; Cl = 35,5. Làm tròn đến hàng phần trăm.)', '8.15', '0.005',
       'n = 4,5 : 45 = 0,1 mol -> m(C2H5NH3Cl) = 0,1 × 81,5 = 8,15 gam.'),

    # ── Polymer ──
    sc(CH4, 'Vật liệu polymer', 'NB', 'Polymer nào sau đây được dùng làm chất dẻo?',
       'Poly(vinyl chloride)', ['Cellulose', 'Nylon-6,6', 'Polybuta-1,3-diene'], 3),
    sc(CH4, 'Đại cương về polymer', 'NB', 'Monomer dùng để điều chế polyethylene (PE) là',
       'CH2=CH2', ['CH2=CHCl', 'CH2=CH–CH3', 'CH2=CH–CH=CH2'], 1),
    sc(CH4, 'Vật liệu polymer', 'TH', 'Tơ nào sau đây thuộc loại tơ tổng hợp?',
       'Nylon-6,6', ['Tơ tằm', 'Bông', 'Tơ visco'], 0,
       'Tơ tằm và bông là tơ tự nhiên; tơ visco là tơ bán tổng hợp.'),
    sc(CH4, 'Đại cương về polymer', 'TH', 'Polymer nào sau đây được điều chế bằng phản ứng trùng ngưng?',
       'Poly(ethylene terephthalate)', ['Polyethylene', 'Poly(vinyl chloride)', 'Polystyrene'], 2),
    sc(CH4, 'Đại cương về polymer', 'VD', 'Một mẫu polyethylene có phân tử khối trung bình là 420 000. '
       'Hệ số polymer hoá trung bình của mẫu này là',
       '15 000', ['12 000', '30 000', '10 000'], 1, 'n = 420 000 : 28 = 15 000.'),
    tf(CH4, 'Đại cương về polymer', 'VD', 'Poly(vinyl chloride) (PVC) được điều chế từ vinyl chloride (CH2=CHCl). '
       'Xét các phát biểu sau (cho H = 1; C = 12; Cl = 35,5):', [
        ('PVC được điều chế bằng phản ứng trùng hợp.', True),
        ('Mỗi mắt xích của PVC có phân tử khối là 62,5.', True),
        ('PVC thuộc loại polymer thiên nhiên.', False),
        ('Một mẫu PVC có phân tử khối trung bình 250 000 chứa trung bình 4 000 mắt xích.', True)],
       '250 000 : 62,5 = 4 000 mắt xích; PVC là polymer tổng hợp.'),
    sa(CH4, 'Đại cương về polymer', 'TH', 'Phân tử khối của một mắt xích trong polystyrene là bao nhiêu? (Cho H = 1; C = 12.)',
       '104', '0', 'Mắt xích –CH2–CH(C6H5)– có công thức C8H8, M = 104.'),
]

# Đề demo: 10 trắc nghiệm × 0,5 + 3 đúng/sai × 1,0 + 4 trả lời ngắn × 0,5 = 10 điểm
EXAM_PICK = {'single_choice': (10, 0.5), 'true_false': (3, 1.0), 'short_answer': (4, 0.5)}


def seed(con, teacher_id, hash_pw, gen_password, t):
    cid = con.execute("INSERT INTO classes(name, year, teacher_id, created_at) VALUES('12A-DEMO','2026–2027',?,?)",
                      (teacher_id, t)).lastrowid
    creds = []
    for i in range(1, 4):
        lid, pw, name = 'demo-hs%02d' % i, gen_password(), 'Học sinh Demo %02d' % i
        sid = con.execute("INSERT INTO users(login_id,name,role,pw,must_change,created_by,created_at) "
                          "VALUES(?,?,'student',?,0,?,?)", (lid, name, hash_pw(pw), teacher_id, t)).lastrowid
        con.execute('INSERT INTO enrollments VALUES(?,?)', (cid, sid))
        creds.append((lid, pw, name))

    ids = []
    for q in QUESTIONS:
        qid = con.execute(
            "INSERT INTO questions(owner_id,status,grade,chapter,topic,level,type,stem,payload,answer_key,explanation,"
            "source,created_at,updated_at) VALUES(?,'approved',?,?,?,?,?,?,?,?,?,?,?,?)",
            (teacher_id, G, q['chapter'], q['topic'], q['level'], q['type'], q['stem'],
             json.dumps(q['payload'], ensure_ascii=False), json.dumps(q['key'], ensure_ascii=False), q['expl'],
             'Câu minh hoạ (DEMO)', t, t)).lastrowid
        ids.append((qid, q))

    eid = con.execute(
        "INSERT INTO exams(owner_id,title,description,start_at,end_at,duration_min,max_attempts,shuffle_q,shuffle_opt,"
        "show_result,tf_policy,status,created_at,published_at) VALUES(?,?,?,?,?,20,3,0,1,'answers','scale','open',?,?)",
        (teacher_id, 'Kiểm tra thử Hoá 12 – Ester, Carbohydrate, Nitrogen, Polymer (DEMO)',
         'Đề minh hoạ: 10 câu trắc nghiệm, 3 câu đúng/sai, 4 câu trả lời ngắn. Được làm 3 lượt.',
         t - 3600, t + 30 * 86400, t, t)).lastrowid
    con.execute('INSERT INTO exam_classes VALUES(?,?)', (eid, cid))
    order = 0
    for tp, (count, pts) in EXAM_PICK.items():
        pool = [(qid, q) for qid, q in ids if q['type'] == tp]
        step = max(1, len(pool) // count)
        for qid, q in pool[::step][:count]:
            snap = {'type': q['type'], 'stem': q['stem'], 'level': q['level'], 'chapter': q['chapter'],
                    'topic': q['topic'], 'grade': G}
            snap.update(q['payload'])
            con.execute('INSERT INTO exam_questions(exam_id,question_id,order_index,points,snapshot,answer_key,explanation) '
                        'VALUES(?,?,?,?,?,?,?)', (eid, qid, order, pts, json.dumps(snap, ensure_ascii=False),
                                                  json.dumps(q['key'], ensure_ascii=False), q['expl']))
            order += 1

    con.execute("INSERT INTO lessons(class_id,teacher_id,title,kind,url,body,published,created_at) VALUES(?,?,?,?,?,?,1,?)",
                (cid, teacher_id, 'Bài 1. Ester – Lipid: tóm tắt lí thuyết (DEMO)', 'note', '',
                 'Ester đơn chức có dạng RCOOR\'.\n'
                 '• Thuỷ phân trong môi trường acid: phản ứng thuận nghịch.\n'
                 '• Thuỷ phân trong môi trường kiềm (xà phòng hoá): phản ứng một chiều.\n'
                 'Ví dụ: CH3COOC2H5 + NaOH -> CH3COONa + C2H5OH.\n\n'
                 'Chất béo là triester của glycerol với acid béo, ví dụ tristearin (C17H35COO)3C3H5.', t))
    con.execute("INSERT INTO lessons(class_id,teacher_id,title,kind,url,body,published,created_at) VALUES(?,?,?,?,?,?,1,?)",
                (cid, teacher_id, 'Bảng tuần hoàn các nguyên tố hoá học – IUPAC (DEMO)', 'link',
                 'https://iupac.org/what-we-do/periodic-table-of-elements/',
                 'Tra cứu tên và kí hiệu nguyên tố theo IUPAC.', t))
    con.execute("INSERT INTO live_sessions(class_id,teacher_id,title,starts_at,duration_min,join_url,note) "
                "VALUES(?,?,?,?,45,?,?)",
                (cid, teacher_id, 'Ôn tập chương Ester – Lipid (DEMO)', t + 86400,
                 'https://meet.google.com/', 'Liên kết minh hoạ — giáo viên thay bằng liên kết phòng học thật.'))
    con.execute("INSERT INTO news(author_id,title,body,pinned,published,created_at) VALUES(?,?,?,1,1,?)",
                (teacher_id, 'Chào mừng đến với TĐH Chemistry',
                 'Đây là lớp học Hoá học số: học sinh nhận bài giảng, lịch học trực tuyến và làm bài kiểm tra ngay trên '
                 'điện thoại hoặc máy tính. Tài khoản do giáo viên cấp.', t))
    con.execute("INSERT INTO news(author_id,title,body,pinned,published,created_at) VALUES(?,?,?,0,1,?)",
                (teacher_id, 'Đề kiểm tra thử Hoá 12 đã mở (DEMO)',
                 'Lớp 12A-DEMO có thể vào mục Bài kiểm tra để làm đề thử. Thời gian làm bài 20 phút, được làm 3 lượt.', t - 60))
    return creds
