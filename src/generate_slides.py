"""Script tạo file thuyết trình PowerPoint (15 slide chuẩn theo hướng dẫn Bài 12).
Tuân thủ chính xác cấu trúc bài thuyết trình 15 phút tại Slide 24 của file Bai12_Huong-dan-bai-tap-lon.pptx.
Tích hợp 100% hình ảnh sơ đồ kiến trúc, lược đồ ERD, biểu đồ phân tích và ảnh chụp giao diện hệ thống thực tế.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

def create_deck():
    prs = Presentation()
    # Tỉ lệ màn hình 16:9 hiện đại
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Bảng màu chuyên nghiệp
    NAVY = RGBColor(15, 23, 42)          # #0f172a
    BLUE = RGBColor(37, 99, 235)         # #2563eb
    DARK_TEXT = RGBColor(30, 41, 59)     # #1e293b
    GRAY_TEXT = RGBColor(100, 116, 139)  # #64748b
    LIGHT_BG = RGBColor(248, 250, 252)   # #f8fafc
    WHITE = RGBColor(255, 255, 255)
    EMERALD = RGBColor(16, 185, 129)     # #10b981
    AMBER = RGBColor(245, 158, 11)       # #f59e0b
    CARD_BG = RGBColor(241, 245, 249)    # #f1f5f9
    BORDER_COL = RGBColor(203, 213, 225) # #cbd5e1

    def add_header(slide, title_text, category_text="HỌC PHẦN INT1422 · KHO DỮ LIỆU & KHAI PHÁ DỮ LIỆU"):
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.733), Inches(1.1))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        
        p_sub = tf.paragraphs[0]
        p_sub.text = category_text.upper()
        p_sub.font.size = Pt(10)
        p_sub.font.bold = True
        p_sub.font.color.rgb = BLUE
        
        p_title = tf.add_paragraph()
        p_title.text = title_text
        p_title.font.size = Pt(21)
        p_title.font.bold = True
        p_title.font.color.rgb = NAVY
        p_title.space_before = Pt(4)

    def add_footer(slide, current_slide, total_slides=15):
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(7.05), Inches(11.733), Inches(0.35))
        tf = footer_box.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = f"Báo cáo Bài tập lớn INT1422 — Nhóm Đề tài Thương mại điện tử đa nguồn | Slide {current_slide}/{total_slides}"
        p.font.size = Pt(9)
        p.font.color.rgb = GRAY_TEXT

    def add_image_panel(slide, img_path, left=6.2, top=1.65, width=6.3, height=5.0, caption=""):
        p_path = Path(img_path)
        if not p_path.exists():
            print(f"Cảnh báo: Không tìm thấy hình ảnh tại {p_path}")
            return
        
        # Thêm khung viền ảnh nền nhạt
        border_rect = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, 
                                             Inches(left - 0.05), Inches(top - 0.05), 
                                             Inches(width + 0.1), Inches(height + 0.1))
        border_rect.fill.solid()
        border_rect.fill.fore_color.rgb = WHITE
        border_rect.line.color.rgb = BORDER_COL
        border_rect.line.width = Pt(1.0)

        # Nhúng ảnh
        slide.shapes.add_picture(str(p_path), Inches(left), Inches(top), Inches(width), Inches(height))

        # Chú thích nhỏ dưới ảnh nếu có
        if caption:
            cbox = slide.shapes.add_textbox(Inches(left), Inches(top + height + 0.02), Inches(width), Inches(0.28))
            tf_c = cbox.text_frame
            tf_c.margin_left = tf_c.margin_top = tf_c.margin_right = tf_c.margin_bottom = 0
            p_c = tf_c.paragraphs[0]
            p_c.text = caption
            p_c.font.size = Pt(8.5)
            p_c.font.italic = True
            p_c.font.color.rgb = GRAY_TEXT
            p_c.alignment = PP_ALIGN.CENTER

    # =========================================================================
    # SLIDE 1: TRANG TIÊU ĐỀ (BÌA BÁO CÁO)
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)
    bg1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = NAVY
    bg1.line.fill.background()

    tbox1 = slide1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(4.5))
    tf1 = tbox1.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "HỌC VIỆN CÔNG NGHỆ BƯU CHÍNH VIỄN THÔNG\nKHOA CÔNG NGHỆ THÔNG TIN 1 · BỘ MÔN HỆ THỐNG THÔNG TIN"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(148, 163, 184)

    p1 = tf1.add_paragraph()
    p1.text = "BÁO CÁO BÀI TẬP LỚN MÔN KHO DỮ LIỆU & KHAI PHÁ DỮ LIỆU"
    p1.font.size = Pt(15)
    p1.font.bold = True
    p1.font.color.rgb = EMERALD
    p1.space_before = Pt(18)

    p2 = tf1.add_paragraph()
    p2.text = "XÂY DỰNG KHO DỮ LIỆU VÀ PHÂN TÍCH BUSINESS INTELLIGENCE\nTHƯƠNG MẠI ĐIỆN TỬ ĐA NGUỒN"
    p2.font.size = Pt(28)
    p2.font.bold = True
    p2.font.color.rgb = WHITE
    p2.space_before = Pt(10)

    p3 = tf1.add_paragraph()
    p3.text = "Chuẩn đầu ra đánh giá: CLO1 (45%) · CLO2 (45%) · CLO3 (10%)\nGiảng viên hướng dẫn: Bộ môn Hệ thống Thông tin | Thời lượng thuyết trình: 15 Phút"
    p3.font.size = Pt(13)
    p3.font.color.rgb = RGBColor(203, 213, 225)
    p3.space_before = Pt(20)

    # =========================================================================
    # SLIDE 2: CÂU HỎI NGHIỆP VỤ & ĐỘNG LỰC ĐỀ TÀI (2 PHÚT)
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    add_header(slide2, "1. Câu Hỏi Nghiệp Vụ & Bối Cảnh Thực Tế Sàn TMĐT", "PHẦN 1: BỐI CẢNH & MỤC TIÊU (2 PHÚT)")
    add_footer(slide2, 2)

    # Cột trái: Vấn đề OLTP vs DWH
    c_left = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.6), Inches(5.15))
    c_left.fill.solid()
    c_left.fill.fore_color.rgb = CARD_BG
    c_left.line.color.rgb = BLUE
    tf_c2 = c_left.text_frame
    tf_c2.word_wrap = True
    tf_c2.margin_left = tf_c2.margin_right = tf_c2.margin_top = Inches(0.25)

    p_t = tf_c2.paragraphs[0]
    p_t.text = "Vấn đề kỹ thuật: CSDL Giao Dịch (OLTP) vs Kho Dữ Liệu (DWH)"
    p_t.font.bold = True
    p_t.font.size = Pt(13.5)
    p_t.font.color.rgb = NAVY

    p_oltp = tf_c2.add_paragraph()
    p_oltp.text = "• Giới hạn của OLTP 3NF truyền thống:\n  - Thiết kế tối ưu cho ghi đơn hàng, khóa bảng liên tục.\n  - Khi chạy các truy vấn tổng hợp doanh thu lớn, gây nghẽn cổ chai và sập luồng bán hàng."
    p_oltp.font.size = Pt(11)
    p_oltp.font.color.rgb = DARK_TEXT
    p_oltp.space_before = Pt(8)

    p_dwh = tf_c2.add_paragraph()
    p_dwh.text = "• Vai trò thiết yếu của Kho dữ liệu (DWH):\n  - Mô hình Kimball Star Schema tách biệt phân tích khỏi vận hành.\n  - Lưu trữ lịch sử đa chiều, tăng tốc tổng hợp đa cấp độ từ O(N) thành O(1)."
    p_dwh.font.size = Pt(11)
    p_dwh.font.color.rgb = DARK_TEXT
    p_dwh.space_before = Pt(8)

    # Cột phải: 3 Câu hỏi nghiệp vụ then chốt
    c_right = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(5.15))
    c_right.fill.solid()
    c_right.fill.fore_color.rgb = CARD_BG
    c_right.line.color.rgb = EMERALD
    tf_cr2 = c_right.text_frame
    tf_cr2.word_wrap = True
    tf_cr2.margin_left = tf_cr2.margin_right = tf_cr2.margin_top = Inches(0.25)

    p_rt = tf_cr2.paragraphs[0]
    p_rt.text = "3 Câu Hỏi Nghiệp Vụ Cần Giải Quyết Bằng DWH & Khai Phá"
    p_rt.font.bold = True
    p_rt.font.size = Pt(13.5)
    p_rt.font.color.rgb = NAVY

    qs = [
        ("Câu hỏi 1 (Kinh doanh & Ngành hàng):", "Doanh thu biến động thế nào theo Năm, Quý, Tháng? Nhóm sản phẩm nào đóng góp doanh thu chủ đạo để chủ động kế hoạch nhập hàng?"),
        ("Câu hỏi 2 (Chăm sóc Khách hàng CRM):", "Những nhóm khách hàng nào là VIP (Champions) đóng góp trên 50% doanh thu? Nhóm nào đang có nguy cơ rời bỏ (At Risk) cần kích cầu?"),
        ("Câu hỏi 3 (Tối ưu Giá trị Đơn hàng AOV):", "Khách hàng khi chọn sản phẩm A thì có xu hướng mua kèm sản phẩm B nào nhất? Thiết kế Combo Bundle thế nào để tăng doanh số bán chéo?")
    ]
    for q_t, q_d in qs:
        p_q = tf_cr2.add_paragraph()
        p_q.text = f"• {q_t}"
        p_q.font.bold = True
        p_q.font.size = Pt(11.5)
        p_q.font.color.rgb = BLUE
        p_q.space_before = Pt(8)
        
        p_qd = tf_cr2.add_paragraph()
        p_qd.text = f"  {q_d}"
        p_qd.font.size = Pt(10.5)
        p_qd.font.color.rgb = DARK_TEXT

    # =========================================================================
    # SLIDE 3: KIẾN TRÚC DỮ LIỆU ĐA NGUỒN (3 PHÚT)
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    add_header(slide3, "2. Kiến Trúc Thu Thập Dữ Liệu Đa Nguồn & Luồng ETL", "PHẦN 2: DỮ LIỆU & TIỀN XỬ LÝ (3 PHÚT)")
    add_footer(slide3, 3)

    # Cột trái: 3 Nguồn dữ liệu thực tế
    b_left3 = slide3.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l3 = b_left3.text_frame
    tf_l3.word_wrap = True
    tf_l3.margin_left = tf_l3.margin_top = tf_l3.margin_right = tf_l3.margin_bottom = 0

    sources_info = [
        ("Nguồn 1: Amazon Reviews 2023", "Cloud HTTP Streaming",
         "Dòng dữ liệu tương tác thực tế từ McAuley-Lab (10,000 dòng, 7,067 SP). Cung cấp user_id, rating, review_text, helpful_vote."),
        ("Nguồn 2: DummyJSON REST API", "RESTful Web Service Động",
         "Thu thập qua HTTP GET có phân trang & Exponential Backoff. Cung cấp 100 User demographics (tuổi, giới tính, địa chỉ) & 50 Carts (194 items)."),
        ("Nguồn 3: Open Food Facts API", "Crowdsourced REST API v2",
         "Làm giàu dữ liệu nguyên liệu (ingredients_text) & nhãn dinh dưỡng cho các sản phẩm thịnh hành, phục vụ thuật toán lọc theo nội dung.")
    ]
    for idx, (s_name, s_type, s_desc) in enumerate(sources_info):
        p_s = tf_l3.paragraphs[0] if idx == 0 else tf_l3.add_paragraph()
        p_s.text = f"• {s_name} [{s_type}]"
        p_s.font.bold = True
        p_s.font.size = Pt(12.5)
        p_s.font.color.rgb = BLUE if idx == 0 else (EMERALD if idx == 1 else AMBER)
        p_s.space_before = Pt(8) if idx > 0 else Pt(0)

        p_sd = tf_l3.add_paragraph()
        p_sd.text = f"  {s_desc}"
        p_sd.font.size = Pt(10.5)
        p_sd.font.color.rgb = DARK_TEXT

    # Cột phải: Hình ảnh Sơ đồ kiến trúc thực tế
    add_image_panel(slide3, ASSETS_DIR / "architecture_diagram.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 1: Sơ đồ kiến trúc tổng thể 4 tầng (Multi-source -> ETL -> DWH Star Schema -> BI & ML)")

    # =========================================================================
    # SLIDE 4: TIỀN XỬ LÝ & KIỂM ĐỊNH CHẤT LƯỢNG (DATA QUALITY)
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    add_header(slide4, "3. Quy Trình Tiền Xử Lý Dữ Liệu & Kiểm Định Toàn Vẹn (100% Passed)", "PHẦN 2: DỮ LIỆU & TIỀN XỬ LÝ (3 PHÚT)")
    add_footer(slide4, 4)

    b_left4 = slide4.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.4), Inches(5.15))
    tf_l4 = b_left4.text_frame
    tf_l4.word_wrap = True
    tf_l4.margin_left = tf_l4.margin_top = tf_l4.margin_right = tf_l4.margin_bottom = 0

    steps_etl = [
        ("1. Làm sạch & Chuẩn hóa Amazon Reviews:", 
         "Loại bỏ bản ghi rỗng user_id/product_id; ép rating vào đoạn [1.0, 5.0]; chuyển đổi millisecond Unix timestamp thành full_timestamp; khử trùng lặp theo cặp (user_id, product_id)."),
        ("2. Ghép nối nhân khẩu học (Entity Resolution):", 
         "Tập hợp user_id duy nhất; thực hiện round-robin ánh xạ hồ sơ nhân khẩu học (tuổi, giới tính, thành phố) từ DummyJSON để tạo tập khách hàng hoàn chỉnh."),
        ("3. Tích hợp đặc trưng SP & Bóc tách thời gian:", 
         "Hợp nhất Metadata sản phẩm với trường ingredients_text từ Open Food Facts; bóc tách full_timestamp thành time_id (YYYYMMDDHH), ngày, tháng, quý, năm, thứ trong tuần."),
        ("4. Kiểm định chất lượng tự động (Quality Gate):", 
         "Chạy src/etl/validate.py trước khi nạp vào DWH: 100% Khóa chính duy nhất; 0 bản ghi mồ côi (Zero Orphan Records) giữa Fact và 4 bảng Dim.")
    ]
    for idx, (st_t, st_d) in enumerate(steps_etl):
        p_st = tf_l4.paragraphs[0] if idx == 0 else tf_l4.add_paragraph()
        p_st.text = f"✓ {st_t}"
        p_st.font.bold = True
        p_st.font.size = Pt(12)
        p_st.font.color.rgb = BLUE if idx < 3 else EMERALD
        p_st.space_before = Pt(6) if idx > 0 else Pt(0)

        p_std = tf_l4.add_paragraph()
        p_std.text = f"  {st_d}"
        p_std.font.size = Pt(10.5)
        p_std.font.color.rgb = DARK_TEXT

    # Cột phải: Bảng kết quả Quality Gate thực tế
    c_right4 = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.5), Inches(1.65), Inches(6.0), Inches(5.15))
    c_right4.fill.solid()
    c_right4.fill.fore_color.rgb = CARD_BG
    c_right4.line.color.rgb = EMERALD
    tf_cr4 = c_right4.text_frame
    tf_cr4.word_wrap = True
    tf_cr4.margin_left = tf_cr4.margin_right = tf_cr4.margin_top = Inches(0.25)

    p_rt4 = tf_cr4.paragraphs[0]
    p_rt4.text = "Báo Cáo Kiểm Định Chất Lượng Tự Động (src/etl/validate.py)"
    p_rt4.font.bold = True
    p_rt4.font.size = Pt(13)
    p_rt4.font.color.rgb = NAVY

    gates = [
        ("Dim_User Validation", "6,585 bản ghi", "Khóa PK user_id 100% duy nhất, 0 NULL. Đầy đủ tuổi, giới tính."),
        ("Dim_Product Validation", "7,067 bản ghi", "Khóa PK product_id 100% duy nhất. Giá bán > $0.00."),
        ("Dim_Category Validation", "3 ngành hàng", "100% Chuẩn hóa danh mục (All Beauty, Appliances, Electronics)."),
        ("Dim_Time Validation", "8,955 mốc giờ", "Khóa time_id dạng YYYYMMDDHH, đủ thứ, ngày, tháng, quý, năm."),
        ("Fact_Interactions Gate", "9,971 tương tác", "TÍNH TOÀN VẸN THAM CHIẾU: 0 Orphan FK (100% user_id, product_id, time_id đều tồn tại hợp lệ trong các bảng Dim tương ứng).")
    ]
    for g_title, g_count, g_desc in gates:
        p_g = tf_cr4.add_paragraph()
        p_g.text = f"🟢 {g_title} ({g_count}):"
        p_g.font.bold = True
        p_g.font.size = Pt(11)
        p_g.font.color.rgb = EMERALD
        p_g.space_before = Pt(6)

        p_gd = tf_cr4.add_paragraph()
        p_gd.text = f"   {g_desc}"
        p_gd.font.size = Pt(10)
        p_gd.font.color.rgb = DARK_TEXT

    # =========================================================================
    # SLIDE 5: THIẾT KẾ LƯỢC ĐỒ HÌNH SAO (STAR SCHEMA DATA MODEL) (4 PHÚT)
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    add_header(slide5, "4. Thiết Kế Lược Đồ Hình Sao (Ralph Kimball Star Schema)", "PHẦN 3: THIẾT KẾ & CÀI ĐẶT KHO DỮ LIỆU (4 PHÚT)")
    add_footer(slide5, 5)

    b_left5 = slide5.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l5 = b_left5.text_frame
    tf_l5.word_wrap = True
    tf_l5.margin_left = tf_l5.margin_top = tf_l5.margin_right = tf_l5.margin_bottom = 0

    p_f5 = tf_l5.paragraphs[0]
    p_f5.text = "• Fact_Interactions (Bảng Sự kiện trung tâm):"
    p_f5.font.bold = True
    p_f5.font.size = Pt(13)
    p_f5.font.color.rgb = NAVY

    p_f5_sub = tf_l5.add_paragraph()
    p_f5_sub.text = "  - Quy mô: 9,971 bản ghi tương tác.\n  - Độ mịn (Granularity): Mỗi dòng là một hành vi (review, cart, purchase) của 1 user với 1 product tại 1 mốc giờ.\n  - Khóa ngoại: user_id, product_id, time_id.\n  - Chỉ số: rating_score, helpful_vote, event_type."
    p_f5_sub.font.size = Pt(10.5)
    p_f5_sub.font.color.rgb = DARK_TEXT
    p_f5_sub.space_before = Pt(3)

    p_d5 = tf_l5.add_paragraph()
    p_d5.text = "• Bốn Bảng Chiều (Dimensions) & Cây Phân Cấp:"
    p_d5.font.bold = True
    p_d5.font.size = Pt(13)
    p_d5.font.color.rgb = BLUE
    p_d5.space_before = Pt(10)

    dims_desc = [
        ("Dim_Time (8,955 dòng):", "Day -> Month -> Quarter -> Year."),
        ("Dim_Category (3 ngành):", "All Beauty, Appliances, Electronics."),
        ("Dim_Product (7,067 SP):", "Product -> Category (Kèm thành phần OFF)."),
        ("Dim_User (6,585 KH):", "User -> City -> Country (Kèm rfm_segment).")
    ]
    for dn, dd in dims_desc:
        p_dn = tf_l5.add_paragraph()
        p_dn.text = f"  - {dn} {dd}"
        p_dn.font.size = Pt(10.5)
        p_dn.font.color.rgb = DARK_TEXT

    # Cột phải: Hình ảnh ERD thực tế
    add_image_panel(slide5, ASSETS_DIR / "star_schema_erd.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 2: Sơ đồ quan hệ thực thể Lược đồ hình sao (Star Schema ERD) với PK và FK liên kết chuẩn Kimball")

    # =========================================================================
    # SLIDE 6: TÍNH TRƯỚC KHỐI ĐA CHIỀU (PRECOMPUTED OLAP CUBES)
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    add_header(slide6, "5. Tính Toán Trước Khối Đa Chiều (GROUP BY CUBE & ROLLUP)", "PHẦN 3: THIẾT KẾ & CÀI ĐẶT KHO DỮ LIỆU (4 PHÚT)")
    add_footer(slide6, 6)

    b_left6 = slide6.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l6 = b_left6.text_frame
    tf_l6.word_wrap = True
    tf_l6.margin_left = tf_l6.margin_top = tf_l6.margin_right = tf_l6.margin_bottom = 0

    p_c1_t = tf_l6.paragraphs[0]
    p_c1_t.text = "1. Khối vw_cube_sales_category_time"
    p_c1_t.font.bold = True
    p_c1_t.font.size = Pt(13)
    p_c1_t.font.color.rgb = BLUE

    p_c1_d = tf_l6.add_paragraph()
    p_c1_d.text = "• Cú pháp: GROUP BY CUBE(c.category_name, t.year, t.quarter)\n• Ý nghĩa nghiệp vụ: Tính toán trước doanh số ở mọi tổ hợp cấp độ: (Danh mục, Năm, Quý), (Danh mục, Năm), (Danh mục), (Năm) và Grand Total (Toàn sàn).\n• Tối ưu hiệu năng: Biến truy vấn O(N) quét bảng Fact thành O(1) đọc trực tiếp từ Khối tính sẵn."
    p_c1_d.font.size = Pt(10.5)
    p_c1_d.font.color.rgb = DARK_TEXT
    p_c1_d.space_before = Pt(3)

    p_c2_t = tf_l6.add_paragraph()
    p_c2_t.text = "2. Khối vw_cube_customer_segment_geo"
    p_c2_t.font.bold = True
    p_c2_t.font.size = Pt(13)
    p_c2_t.font.color.rgb = EMERALD
    p_c2_t.space_before = Pt(10)

    p_c2_d = tf_l6.add_paragraph()
    p_c2_d.text = "• Cú pháp: GROUP BY ROLLUP(u.rfm_segment, u.country, u.city)\n• Ý nghĩa nghiệp vụ: Phân tích khách hàng theo cây phân cấp địa lý: Phân khúc -> Quốc gia -> Thành phố sinh sống.\n• Phục vụ Marketing: Phân bổ ngân sách khuyến mại chính xác vào các thành phố tập trung khách VIP."
    p_c2_d.font.size = Pt(10.5)
    p_c2_d.font.color.rgb = DARK_TEXT
    p_c2_d.space_before = Pt(3)

    # Cột phải: Hình ảnh Roll-up và Heatmap thực tế
    add_image_panel(slide6, ASSETS_DIR / "olap_pivot_heatmap.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 3: Kết quả tổng hợp đa chiều từ khối tính trước: Roll-up Doanh thu theo Quý & Pivot Heatmap")

    # =========================================================================
    # SLIDE 7: BÁO CÁO DOANH NGHIỆP & PHỄU CHUYỂN ĐỔI (BI DASHBOARD)
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    add_header(slide7, "6. Báo Cáo Hiệu Năng Doanh Nghiệp (Executive BI Dashboard)", "PHẦN 4: DỊCH VỤ OLAP & TRỰC QUAN HÓA (4 PHÚT)")
    add_footer(slide7, 7)

    b_left7 = slide7.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l7 = b_left7.text_frame
    tf_l7.word_wrap = True
    tf_l7.margin_left = tf_l7.margin_top = tf_l7.margin_right = tf_l7.margin_bottom = 0

    p_kpi_t = tf_l7.paragraphs[0]
    p_kpi_t.text = "• 4 Chỉ Số Hiệu Năng Cốt Lõi (DWH KPIs):"
    p_kpi_t.font.bold = True
    p_kpi_t.font.size = Pt(13)
    p_kpi_t.font.color.rgb = NAVY

    kpi_lines = [
        ("Tổng Doanh Thu DWH:", "$199,320.29 USD"),
        ("Tổng Tương Tác Đơn Hàng:", "9,971 lượt giao dịch"),
        ("Tổng Khách Hàng Quản Trị:", "6,585 người dùng"),
        ("Đánh Giá Trung Bình Toàn Sàn:", "4.25 / 5.0 Sao")
    ]
    for kl, kv in kpi_lines:
        p_kl = tf_l7.add_paragraph()
        p_kl.text = f"  - {kl} "
        p_kl.font.size = Pt(11)
        p_kl.font.color.rgb = DARK_TEXT
        # Append bold value
        r = p_kl.add_run()
        r.text = kv
        r.font.bold = True
        r.font.color.rgb = EMERALD if "$" in kv else BLUE

    p_bi_a = tf_l7.add_paragraph()
    p_bi_a.text = "• Phân Tích Xu Hướng & Phễu Chuyển Đổi:"
    p_bi_a.font.bold = True
    p_bi_a.font.size = Pt(13)
    p_bi_a.font.color.rgb = NAVY
    p_bi_a.space_before = Pt(8)

    p_bi_sub = tf_l7.add_paragraph()
    p_bi_sub.text = "  - Doanh thu theo tháng (vw_sales_monthly_summary) phản ánh nhịp độ mua sắm mùa vụ của khách hàng.\n  - Phễu chuyển đổi 4 tầng: Tiếp cận (6,585 Users) -> Xem SP (7,067 Prods) -> Thêm giỏ (1,394 Carts) -> Đánh giá (9,971 Reviews), cho thấy mức độ gắn kết cao của người dùng."
    p_bi_sub.font.size = Pt(10.5)
    p_bi_sub.font.color.rgb = DARK_TEXT
    p_bi_sub.space_before = Pt(3)

    # Cột phải: Ảnh chụp thực tế Tab 1 Streamlit
    add_image_panel(slide7, ASSETS_DIR / "ui_tab1_bi_overview.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 4: Ảnh chụp thực tế giao diện Streamlit Tab 1 (Báo cáo Hiệu năng Doanh nghiệp & Phễu tương tác)")

    # =========================================================================
    # SLIDE 8: TRÌNH DIỄN ĐỦ 5 THAO TÁC OLAP TRỰC TIẾP (LIVE OLAP DEMO)
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    add_header(slide8, "7. Trình Diễn Đủ 5 Thao Tác OLAP Trực Tiếp Trên Web Dashboard", "PHẦN 4: DỊCH VỤ OLAP & TRỰC QUAN HÓA (4 PHÚT)")
    add_footer(slide8, 8)

    b_left8 = slide8.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l8 = b_left8.text_frame
    tf_l8.word_wrap = True
    tf_l8.margin_left = tf_l8.margin_top = tf_l8.margin_right = tf_l8.margin_bottom = 0

    olap_ops_list = [
        ("1. ROLL-UP (Thu gọn / Tổng hợp):", "Thu gọn từ Tháng -> Quý -> Năm hoặc từ Sản phẩm -> Danh mục để xem tổng doanh số toàn sàn."),
        ("2. DRILL-DOWN (Chi tiết hóa):", "Đi sâu từ Danh mục sản phẩm (All Beauty) xuống danh sách 15 sản phẩm bán chạy nhất kèm giá bán và rating."),
        ("3. SLICE (Cắt lát đơn):", "Cố định 1 chiều: Cắt lát dữ liệu theo Mức Đánh Giá = 5.0 Sao hoặc Cố định Quý 3 để khảo sát đơn hàng hoàn hảo."),
        ("4. DICE (Cắt khối đa chiều):", "Lọc đồng thời trên 2 chiều: Chiều Thời gian (Năm 2022, 2023) VÀ Chiều Sản phẩm (Khoảng giá từ $10 đến $60)."),
        ("5. PIVOT (Xoay ma trận):", "Xoay trục hiển thị: Danh mục thành Hàng và Năm thành Cột, hiển thị bảng chéo kèm Heatmap doanh thu.")
    ]
    for idx, (op_name, op_desc) in enumerate(olap_ops_list):
        p_op = tf_l8.paragraphs[0] if idx == 0 else tf_l8.add_paragraph()
        p_op.text = f"• {op_name}"
        p_op.font.bold = True
        p_op.font.size = Pt(11.5)
        p_op.font.color.rgb = BLUE if idx % 2 == 0 else EMERALD
        p_op.space_before = Pt(5) if idx > 0 else Pt(0)

        p_opd = tf_l8.add_paragraph()
        p_opd.text = f"  {op_desc}"
        p_opd.font.size = Pt(10)
        p_opd.font.color.rgb = DARK_TEXT

    # Cột phải: Ảnh chụp thực tế Tab 2 Streamlit
    add_image_panel(slide8, ASSETS_DIR / "ui_tab2_olap_ops.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 5: Ảnh chụp thực tế giao diện Streamlit Tab 2 (Trình diễn trực tiếp 5 thao tác OLAP trên CSDL DWH)")

    # =========================================================================
    # SLIDE 9: KHAI PHÁ DỮ LIỆU - PHÂN CỤM KHÁCH HÀNG RFM (K-MEANS) (4 PHÚT)
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    add_header(slide9, "8. Khai Phá Dữ Liệu: Phân Cụm Khách Hàng RFM (K-Means Clustering)", "PHẦN 5: CHỨC NĂNG KHAI PHÁ DỮ LIỆU (4 PHÚT)")
    add_footer(slide9, 9)

    b_left9 = slide9.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l9 = b_left9.text_frame
    tf_l9.word_wrap = True
    tf_l9.margin_left = tf_l9.margin_top = tf_l9.margin_right = tf_l9.margin_bottom = 0

    rfm_steps = [
        ("1. Vector đặc trưng RFM:", "Recency (Số ngày kể từ lần tương tác gần nhất); Frequency (Tổng số lần mua/đánh giá); Monetary (Tổng chi tiêu tích lũy)."),
        ("2. Chuẩn hóa phân phối chuẩn:", "Sử dụng StandardScaler đưa R, F, M có biên độ lệch nhau về cùng thang phân phối chuẩn N(0, 1)."),
        ("3. Đánh giá số cụm K tối ưu:", "Đo lường bằng phương pháp Elbow và Silhouette Score. Đạt đỉnh Silhouette = 0.6393 tại K = 4 (Phản ánh phân tách giữa các cụm rất tốt và cấu trúc đậm đặc)."),
        ("4. Đóng gói ngược vào DWH (Closed-loop):", "Gán nhãn phân cụm tự động vào cột rfm_segment của Dim_User trong PostgreSQL để phục vụ phân tích OLAP tức thì.")
    ]
    for idx, (rt, rd) in enumerate(rfm_steps):
        p_r = tf_l9.paragraphs[0] if idx == 0 else tf_l9.add_paragraph()
        p_r.text = f"• {rt}"
        p_r.font.bold = True
        p_r.font.size = Pt(12)
        p_r.font.color.rgb = BLUE
        p_r.space_before = Pt(6) if idx > 0 else Pt(0)

        p_rd = tf_l9.add_paragraph()
        p_rd.text = f"  {rd}"
        p_rd.font.size = Pt(10.5)
        p_rd.font.color.rgb = DARK_TEXT

    # Cột phải: Biểu đồ Silhouette Score & Pie Chart thực tế
    add_image_panel(slide9, ASSETS_DIR / "rfm_clusters_vis.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 6: Biểu đồ Tỷ trọng Doanh thu 4 cụm RFM & Đường cong Silhouette Score đạt K=4 tối ưu")

    # =========================================================================
    # SLIDE 10: ĐẶC TRƯNG 4 PHÂN KHÚC & CHIẾN LƯỢC TIẾP THỊ
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    add_header(slide10, "9. Chân Dung 4 Phân Khúc Khách Hàng & Chiến Lược Hành Động", "PHẦN 5: CHỨC NĂNG KHAI PHÁ DỮ LIỆU (4 PHÚT)")
    add_footer(slide10, 10)

    b_left10 = slide10.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l10 = b_left10.text_frame
    tf_l10.word_wrap = True
    tf_l10.margin_left = tf_l10.margin_top = tf_l10.margin_right = tf_l10.margin_bottom = 0

    segs = [
        ("1. Champions (VIP) — 30.2% Doanh thu:", "Chi tiêu cao nhất (ARPU $286.65), mua gần nhất. Hành động: Chăm sóc đặc quyền VIP, quà tri ân, quyền mua sớm."),
        ("2. Potential Loyalists — 22.9% Doanh thu:", "Mới tương tác gần đây với giá trị đơn triển vọng. Hành động: Tặng voucher đơn hàng thứ 2, gợi ý sản phẩm phù hợp."),
        ("3. Loyal Customers — Mua sắm định kỳ:", "Mức độ gắn kết cao, đơn hàng đều đặn. Hành động: Tích điểm loyalty, gợi ý ngành hàng mới qua Cross-sell."),
        ("4. At Risk / Inactive — 47.0% Khách hàng:", "Đã lâu không quay lại sàn (Recency lớn). Hành động: Chiến dịch Re-engagement kích cầu, giảm giá sâu tái kích hoạt.")
    ]
    for idx, (st, sd) in enumerate(segs):
        p_s = tf_l10.paragraphs[0] if idx == 0 else tf_l10.add_paragraph()
        p_s.text = f"• {st}"
        p_s.font.bold = True
        p_s.font.size = Pt(11.5)
        p_s.font.color.rgb = AMBER if idx == 0 else (BLUE if idx == 1 else (EMERALD if idx == 2 else RGBColor(244, 63, 94)))
        p_s.space_before = Pt(6) if idx > 0 else Pt(0)

        p_sd = tf_l10.add_paragraph()
        p_sd.text = f"  {sd}"
        p_sd.font.size = Pt(10)
        p_sd.font.color.rgb = DARK_TEXT

    # Cột phải: Ảnh chụp thực tế Tab 3 Streamlit
    add_image_panel(slide10, ASSETS_DIR / "ui_tab3_rfm_segments.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 7: Ảnh chụp thực tế giao diện Streamlit Tab 3 (Dashboard Phân khúc RFM & Chỉ số ARPU)")

    # =========================================================================
    # SLIDE 11: KHAI PHÁ LUẬT KẾT HỢP GIỎ HÀNG (FP-GROWTH)
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    add_header(slide11, "10. Khai Phá Luật Kết Hợp Giỏ Hàng (FP-Growth Association Rules)", "PHẦN 5: CHỨC NĂNG KHAI PHÁ DỮ LIỆU (4 PHÚT)")
    add_footer(slide11, 11)

    b_left11 = slide11.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l11 = b_left11.text_frame
    tf_l11.word_wrap = True
    tf_l11.margin_left = tf_l11.margin_top = tf_l11.margin_right = tf_l11.margin_bottom = 0

    mba_points = [
        ("1. Dữ liệu giỏ hàng (Market Basket Data):", "Kết hợp từ các giỏ hàng thực tế của DummyJSON Carts (194 mặt hàng) và nhóm các sản phẩm được cùng một người dùng mua trên sàn."),
        ("2. Thuật toán FP-Growth nén cây FP-Tree:", "Khai phá nhanh vượt trội so với Apriori truyền thống vì không phải quét lại CSDL nhiều lần."),
        ("3. Bắt buộc kiểm tra chỉ số Độ nâng (Lift) — Slide 25:", "Thiết lập ngưỡng min_support = 0.005, min_confidence = 0.1 và min_lift >= 1.1. Trích xuất thành công 7,674 luật kết hợp có Lift lên đến 60.0x!"),
        ("4. Ứng dụng tạo gói ưu đãi Combo (Bundle Offer):", "Ví dụ: Luật [Cat Food, Cricket Ball] => [Tropical Earring] đạt Lift = 60.0x (Xác suất mua kèm cao gấp 60 lần so với ngẫu nhiên). Ứng dụng ngay vào giảm giá Combo -10%.")
    ]
    for idx, (mt, md) in enumerate(mba_points):
        p_m = tf_l11.paragraphs[0] if idx == 0 else tf_l11.add_paragraph()
        p_m.text = f"• {mt}"
        p_m.font.bold = True
        p_m.font.size = Pt(11.5)
        p_m.font.color.rgb = EMERALD
        p_m.space_before = Pt(6) if idx > 0 else Pt(0)

        p_md = tf_l11.add_paragraph()
        p_md.text = f"  {md}"
        p_md.font.size = Pt(10)
        p_md.font.color.rgb = DARK_TEXT

    # Cột phải: Ảnh chụp thực tế Tab 4 Streamlit
    add_image_panel(slide11, ASSETS_DIR / "ui_tab4_cross_sell.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 8: Ảnh chụp thực tế giao diện Streamlit Tab 4 (Khai phá 7,674 luật kết hợp với Lift tới 60x)")

    # =========================================================================
    # SLIDE 12: ĐÁNH GIÁ OFFLINE & SO SÁNH VỚI BASELINE (SLIDE 25)
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    add_header(slide12, "11. Đánh Giá Offline Hệ Thống Gợi Ý & So Sánh Mô Hình Cơ Sở", "PHẦN 5: CHỨC NĂNG KHAI PHÁ DỮ LIỆU (4 PHÚT)")
    add_footer(slide12, 12)

    b_left12 = slide12.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l12 = b_left12.text_frame
    tf_l12.word_wrap = True
    tf_l12.margin_left = tf_l12.margin_top = tf_l12.margin_right = tf_l12.margin_bottom = 0

    eval_items = [
        ("1. Temporal Split (Phân chia theo thời gian):", "Dữ liệu quá khứ dùng huấn luyện, 20% giao dịch gần nhất dùng kiểm thử trên 874 người dùng (Tránh rò rỉ dữ liệu)."),
        ("2. So sánh với Mô hình Cơ sở (Slide 25):", "Không báo cáo mô hình đơn lẻ. Đối chiếu đồng thời: Popularity Baseline, TruncatedSVD (CF) và Content-Based (TF-IDF + Open Food Facts)."),
        ("3. Kết quả đánh giá xếp hạng tại K = 10:", "• Popularity Baseline: Recall@10 = 0.0160 | NDCG@10 = 0.0074 | HitRate = 1.60%\n• Content-Based: Recall@10 = 0.0023 | NDCG@10 = 0.0015 | MAP@10 = 0.0013\n• SVD (CF): Recall@10 = 0.0034 | NDCG@10 = 0.0015 | HitRate = 0.34%"),
        ("4. Nhận định học thuật về Độ thưa (Sparsity = 99.98%):", "Dữ liệu TMĐT thực tế cực thưa (1.30 tương tác/user). SVD gặp Cold-Start nặng; Content-Based có lợi thế vượt trội khi tích hợp thành phần Open Food Facts.")
    ]
    for idx, (et, ed) in enumerate(eval_items):
        p_e = tf_l12.paragraphs[0] if idx == 0 else tf_l12.add_paragraph()
        p_e.text = f"• {et}"
        p_e.font.bold = True
        p_e.font.size = Pt(11.5)
        p_e.font.color.rgb = NAVY
        p_e.space_before = Pt(6) if idx > 0 else Pt(0)

        p_ed = tf_l12.add_paragraph()
        p_ed.text = f"  {ed}"
        p_ed.font.size = Pt(10)
        p_ed.font.color.rgb = DARK_TEXT

    # Cột phải: Biểu đồ Benchmark offline thực tế
    add_image_panel(slide12, ASSETS_DIR / "recsys_benchmark_vis.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 9: So sánh hiệu năng Offline giữa Popularity Baseline, Content-Based và CF-SVD tại K=10")

    # =========================================================================
    # SLIDE 13: ỨNG DỤNG THỰC TẾ - COMBO MUA KÈM & BÁN CHÉO (CROSS-SELL) (2 PHÚT)
    # =========================================================================
    slide13 = prs.slides.add_slide(blank_layout)
    add_header(slide13, "12. Ứng Dụng Thực Tế: Gói Ưu Đãi Mua Kèm & Gợi Ý Cá Nhân Hóa", "PHẦN 6: KHUYẾN NGHỊ & HÀNH ĐỘNG (2 PHÚT)")
    add_footer(slide13, 13)

    b_left13 = slide13.shapes.add_textbox(Inches(0.8), Inches(1.65), Inches(5.1), Inches(5.15))
    tf_l13 = b_left13.text_frame
    tf_l13.word_wrap = True
    tf_l13.margin_left = tf_l13.margin_top = tf_l13.margin_right = tf_l13.margin_bottom = 0

    apps_list = [
        ("1. Tích hợp trực tiếp Luật Kết Hợp vào Giỏ hàng:", "Hệ thống tự động tra cứu các luật có Lift cao nhất để đề xuất các sản phẩm mua kèm thường đi cùng."),
        ("2. Gói ưu đãi Combo (Bundle Discount - Tiết kiệm 10%):", "Tự động gom Combo sản phẩm liên quan và chiết khấu ngay 10% để kích thích người dùng hoàn tất đơn hàng giá trị cao hơn (Tăng AOV)."),
        ("3. Gợi ý cá nhân hóa theo phân khúc RFM:", "Khách Champions được gợi ý sản phẩm cao cấp, khách Potential Loyalists được gợi ý các mặt hàng bán chạy nhất."),
        ("4. Trải nghiệm trực quan trên Web Dashboard:", "Giao diện Streamlit cho phép người dùng chọn thử bất kỳ sản phẩm nào để xem kết quả tính toán động thời gian thực.")
    ]
    for idx, (at, ad) in enumerate(apps_list):
        p_a = tf_l13.paragraphs[0] if idx == 0 else tf_l13.add_paragraph()
        p_a.text = f"• {at}"
        p_a.font.bold = True
        p_a.font.size = Pt(11.5)
        p_a.font.color.rgb = BLUE
        p_a.space_before = Pt(6) if idx > 0 else Pt(0)

        p_ad = tf_l13.add_paragraph()
        p_ad.text = f"  {ad}"
        p_ad.font.size = Pt(10)
        p_ad.font.color.rgb = DARK_TEXT

    # Cột phải: Ảnh chụp thực tế Gói Combo Bundle trên Web
    add_image_panel(slide13, ASSETS_DIR / "ui_tab4_bundle_cards.png", 
                    left=6.1, top=1.65, width=6.4, height=5.1, 
                    caption="Hình 10: Ảnh chụp thực tế các thẻ Gói sản phẩm mua kèm Combo (Bundle Recommendation) trên Web")

    # =========================================================================
    # SLIDE 14: KIẾN TRÚC MỘT LỆNH & HẠN CHẾ CỦA ĐỀ TÀI
    # =========================================================================
    slide14 = prs.slides.add_slide(blank_layout)
    add_header(slide14, "13. Tự Động Hóa Vận Hành Bằng Một Lệnh & Hạn Chế Của Nhóm", "PHẦN 6: KHUYẾN NGHỊ & HÀNH ĐỘNG (2 PHÚT)")
    add_footer(slide14, 14)

    # Cột trái: Khả năng tái lập 1 lệnh duy nhất (Slide 12)
    c_left14 = slide14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.6), Inches(5.15))
    c_left14.fill.solid()
    c_left14.fill.fore_color.rgb = CARD_BG
    c_left14.line.color.rgb = EMERALD
    tf_c14 = c_left14.text_frame
    tf_c14.word_wrap = True
    tf_c14.margin_left = tf_c14.margin_right = tf_c14.margin_top = Inches(0.25)

    p_run = tf_c14.paragraphs[0]
    p_run.text = "✓ Tái Lập 100% Bằng 1 Lệnh Duy Nhất (Slide 12)"
    p_run.font.bold = True
    p_run.font.size = Pt(13.5)
    p_run.font.color.rgb = NAVY

    p_run_sub = tf_c14.add_paragraph()
    p_run_sub.text = "• Lệnh thực thi: python run_all.py\n\n• Toàn bộ 6 giai đoạn tự động chạy khép kín trong < 10 giây:\n  1. Khởi tạo cấu trúc Star Schema CSDL (PostgreSQL)\n  2. Trích xuất đa nguồn (Amazon, DummyJSON, Open Food Facts)\n  3. Tiền xử lý, khử trùng lặp & Quality Gate 100% Passed\n  4. Tính toán trước 2 Khối đa chiều (CUBE & ROLLUP)\n  5. Huấn luyện K-Means RFM & FP-Growth Market Basket\n  6. Tự động khởi chạy Web BI Dashboard trên cổng 8501\n\n• Giúp Giảng viên và Hội đồng kiểm chứng kết quả minh bạch tuyệt đối!"
    p_run_sub.font.size = Pt(10.5)
    p_run_sub.font.color.rgb = DARK_TEXT
    p_run_sub.space_before = Pt(8)

    # Cột phải: 3 Hạn chế trung thực của đề tài (Slide 24)
    c_right14 = slide14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(5.15))
    c_right14.fill.solid()
    c_right14.fill.fore_color.rgb = CARD_BG
    c_right14.line.color.rgb = AMBER
    tf_cr14 = c_right14.text_frame
    tf_cr14.word_wrap = True
    tf_cr14.margin_left = tf_cr14.margin_right = tf_cr14.margin_top = Inches(0.25)

    p_lim_t = tf_cr14.paragraphs[0]
    p_lim_t.text = "⚠️ Các Hạn Chế Trung Thực Của Đề Tài (Slide 24)"
    p_lim_t.font.bold = True
    p_lim_t.font.size = Pt(13.5)
    p_lim_t.font.color.rgb = NAVY

    lims = [
        ("1. Giới hạn Rate Limiting của REST API:", "Do gọi qua các API công cộng miễn phí (DummyJSON, Open Food Facts), nhóm phải giới hạn tần suất và quy mô mẫu ~10,000 bản ghi để đảm bảo tốc độ demo."),
        ("2. Độ thưa dữ liệu tương tác cao (99.98%):", "Khách hàng Amazon trong tập dữ liệu phần lớn chỉ có 1 tương tác, gây khó khăn cho mô hình phân rã ma trận ẩn SVD (bài toán Cold-Start)."),
        ("3. Môi trường tính toán cục bộ:", "DWH hiện tại chạy trên Docker container máy cá nhân, chưa được triển khai trên cụm máy chủ phân tán Cloud (AWS Redshift / Snowflake).")
    ]
    for lt, ld in lims:
        p_l = tf_cr14.add_paragraph()
        p_l.text = f"• {lt}"
        p_l.font.bold = True
        p_l.font.size = Pt(11)
        p_l.font.color.rgb = AMBER
        p_l.space_before = Pt(8)

        p_ld = tf_cr14.add_paragraph()
        p_ld.text = f"  {ld}"
        p_ld.font.size = Pt(10)
        p_ld.font.color.rgb = DARK_TEXT

    # =========================================================================
    # SLIDE 15: HƯỚNG PHÁT TRIỂN & TỔNG KẾT (Q&A)
    # =========================================================================
    slide15 = prs.slides.add_slide(blank_layout)
    add_header(slide15, "14. Hướng Phát Triển Mở Rộng & Tổng Kết Đồ Án", "PHẦN 6: KHUYẾN NGHỊ & HÀNH ĐỘNG (2 PHÚT)")
    add_footer(slide15, 15)

    # Cột trái: Hướng phát triển
    c_left15 = slide15.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(5.6), Inches(5.15))
    c_left15.fill.solid()
    c_left15.fill.fore_color.rgb = CARD_BG
    c_left15.line.color.rgb = BLUE
    tf_c15 = c_left15.text_frame
    tf_c15.word_wrap = True
    tf_c15.margin_left = tf_c15.margin_right = tf_c15.margin_top = Inches(0.25)

    p_dev = tf_c15.paragraphs[0]
    p_dev.text = "• Hướng Phát Triển Tiếp Theo Trong Thực Tế"
    p_dev.font.bold = True
    p_dev.font.size = Pt(13.5)
    p_dev.font.color.rgb = NAVY

    devs = [
        ("1. Streaming Ingestion thời gian thực:", "Tích hợp Apache Kafka và Apache Flink để bắt sự kiện tương tác giỏ hàng (Clickstream) theo thời gian thực."),
        ("2. Mô hình Deep Learning Recommender:", "Thử nghiệm kiến trúc Two-Tower DNN hoặc Graph Neural Networks (GNN) để nắm bắt mối quan hệ phi tuyến tính phức tạp."),
        ("3. MLOps Pipeline tự động hóa:", "Sử dụng Apache Airflow để lập lịch tự động huấn luyện lại K-Means và FP-Growth định kỳ hàng tuần.")
    ]
    for dt, dd in devs:
        p_d = tf_c15.add_paragraph()
        p_d.text = f"• {dt}"
        p_d.font.bold = True
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = BLUE
        p_d.space_before = Pt(8)

        p_dd = tf_c15.add_paragraph()
        p_dd.text = f"  {dd}"
        p_dd.font.size = Pt(10)
        p_dd.font.color.rgb = DARK_TEXT

    # Cột phải: Đối chiếu 3 Chuẩn đầu ra CLO & Cảm ơn
    c_right15 = slide15.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.65), Inches(5.7), Inches(5.15))
    c_right15.fill.solid()
    c_right15.fill.fore_color.rgb = CARD_BG
    c_right15.line.color.rgb = EMERALD
    tf_cr15 = c_right15.text_frame
    tf_cr15.word_wrap = True
    tf_cr15.margin_left = tf_cr15.margin_right = tf_cr15.margin_top = Inches(0.25)

    p_clo = tf_cr15.paragraphs[0]
    p_clo.text = "✓ Tóm Tắt Kết Quả Đạt Được (Đối Chiếu Chuẩn Đầu Ra)"
    p_clo.font.bold = True
    p_clo.font.size = Pt(13.5)
    p_clo.font.color.rgb = NAVY

    clos = [
        ("CLO1 (45%): Kho Dữ Liệu & OLAP", "Hoàn thành Lược đồ hình sao (1 Fact + 4 Dim), tính trước 2 Khối đa chiều (CUBE & ROLLUP), trình diễn đầy đủ 5 thao tác OLAP trên giao diện Web."),
        ("CLO2 (45%): Khai Phá Dữ Liệu & Đánh Giá", "Thực hiện thành công 2 bài toán chuẩn: Phân cụm RFM (Silhouette = 0.6393 tại K=4) & Luật kết hợp FP-Growth (7,674 luật, Lift tới 60.0x); Có đánh giá Offline đa mô hình so với Baseline."),
        ("CLO3 (10%): Kỹ Năng Dự Án & Tự Động Hóa", "Vận hành bằng 1 lệnh duy nhất python run_all.py; Quản trị phiên bản Git minh bạch; Báo cáo slide 15 trang chuẩn mực.")
    ]
    for ct, cd in clos:
        p_c = tf_cr15.add_paragraph()
        p_c.text = f"• {ct}"
        p_c.font.bold = True
        p_c.font.size = Pt(11)
        p_c.font.color.rgb = EMERALD
        p_c.space_before = Pt(8)

        p_cd = tf_cr15.add_paragraph()
        p_cd.text = f"  {cd}"
        p_cd.font.size = Pt(10)
        p_cd.font.color.rgb = DARK_TEXT

    p_qa = tf_cr15.add_paragraph()
    p_qa.text = "NHÓM XIN TRÂN TRỌNG CẢM ƠN THẦY CÔ VÀ HỘI ĐỒNG!\n(SẴN SÀNG CHO PHẦN HỎI ĐÁP - Q&A)"
    p_qa.font.bold = True
    p_qa.font.size = Pt(12)
    p_qa.font.color.rgb = NAVY
    p_qa.space_before = Pt(16)
    p_qa.alignment = PP_ALIGN.CENTER

    # Lưu file deck
    out_path = PROJECT_ROOT / "Bao_Cao_Thuyet_Trinh_INT1422.pptx"
    prs.save(str(out_path))
    print(f" ĐÃ TẠO THÀNH CÔNG FILE SLIDE 15 TRANG TÍCH HỢP HÌNH ẢNH THỰC TẾ TẠI: {out_path}")

if __name__ == "__main__":
    create_deck()
