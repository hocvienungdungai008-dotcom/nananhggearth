import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image
import os
from osgeo import gdal, osr

# Cấu hình trang mở rộng tối đa (wide layout)
st.set_page_config(page_title="Tool Georeferencing Lưới Điện", layout="wide")

# Khởi tạo các biến nhớ (session state)
if 'gcp_list' not in st.session_state:
    st.session_state['gcp_list'] = []
if 'last_pixel' not in st.session_state:
    st.session_state['last_pixel'] = None

# ==========================================
# KHU VỰC 1: THANH BÊN (SIDEBAR) - BẢNG ĐIỀU KHIỂN
# ==========================================
with st.sidebar:
    st.title("⚙️ Bảng Điều Khiển")
    
    # 1. Khu vực Upload (Gọn gàng trên cùng)
    uploaded_file = st.file_uploader("1. Tải sơ đồ (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    # Chỉ hiện thanh Zoom và Form nhập khi đã có ảnh
    zoom_level = 800 # Giá trị mặc định
    if uploaded_file:
        st.divider()
        st.subheader("🔍 Công cụ Zoom")
        # Thanh trượt chỉnh kích thước ảnh hiển thị (Tối đa 3000px)
        zoom_level = st.slider("Kéo để phóng to/thu nhỏ ảnh", min_value=500, max_value=3000, value=1000, step=100)

        st.divider()
        st.subheader("2. Nhập Tọa độ Thực tế")
        lat = st.number_input("Kinh độ (Longitude / X)", format="%.6f", value=0.0)
        lon = st.number_input("Vĩ độ (Latitude / Y)", format="%.6f", value=0.0)
        
        # Nút thêm điểm mốc chiếm toàn bộ chiều ngang sidebar
        if st.button("➕ Thêm điểm mốc này", type="primary", use_container_width=True):
            if st.session_state['last_pixel'] is None:
                st.error("⚠️ Hãy click chọn điểm trên ảnh ở màn hình chính trước!")
            elif lat == 0.0 or lon == 0.0:
                st.error("⚠️ Hãy nhập Kinh độ / Vĩ độ!")
            else:
                px, py = st.session_state['last_pixel']
                st.session_state['gcp_list'].append({
                    'Pixel_X': px, 'Pixel_Y': py, 'Kinh độ': lat, 'Vĩ độ': lon
                })
                st.session_state['last_pixel'] = None # Xóa nhớ điểm cũ
                st.rerun()

        st.divider()
        st.subheader(f"3. Danh sách mốc ({len(st.session_state['gcp_list'])} điểm)")
        if st.session_state['gcp_list']:
            # Dùng st.dataframe để bảng cuộn được, tiết kiệm diện tích hơn st.table
            st.dataframe(st.session_state['gcp_list'], hide_index=True) 
            if st.button("🗑️ Xóa toàn bộ", use_container_width=True):
                st.session_state['gcp_list'] = []
                st.rerun()

# ==========================================
# KHU VỰC 2: MÀN HÌNH CHÍNH - HIỂN THỊ ẢNH
# ==========================================
st.title("📍 Khu Vực Chấm Điểm Sơ Đồ")

if not uploaded_file:
    st.info("👈 Vui lòng tải một bức ảnh sơ đồ ở thanh công cụ bên trái để bắt đầu.")
else:
    # Mở và lưu file tạm
    img = Image.open(uploaded_file)
    img_path = "input_temp.jpg"
    img.save(img_path)

    # Hiển thị thông báo hướng dẫn
    if st.session_state['last_pixel'] is None:
        st.info("👆 Hãy di chuột và CLICK vào một vị trí trên ảnh. Dùng thanh trượt 'Zoom' bên trái để nhìn rõ hơn.")
    else:
        st.success(f"🎯 Đã khóa mục tiêu Pixel: {st.session_state['last_pixel']}. Sang cột bên trái nhập tọa độ WGS84 và bấm Thêm!")

    # HIỂN THỊ ẢNH VỚI TÍNH NĂNG ZOOM (thông qua tham số width)
    value = streamlit_image_coordinates(img, width=zoom_level, key="image_coords")
    
    # Bắt sự kiện click
    if value and (st.session_state['last_pixel'] is None or st.session_state['last_pixel'] != (value['x'], value['y'])):
        st.session_state['last_pixel'] = (value['x'], value['y'])
        st.rerun()

    st.divider()
    
    # 4. Nút Xuất File (Nằm dưới cùng màn hình chính, to và rõ)
    if len(st.session_state['gcp_list']) >= 3:
        if st.button("🚀 XUẤT FILE GEOTIFF ĐỂ XEM TRÊN GOOGLE EARTH", type="primary", use_container_width=True):
            try:
                with st.spinner("Đang xử lý nắn ảnh bằng GDAL..."):
                    output_tif = "output_map.tif"
                    temp_vrt = "temp.vrt"

                    gcps = []
                    for p in st.session_state['gcp_list']:
                        gcps.append(gdal.GCP(p['Kinh độ'], p['Vĩ độ'], 0, p['Pixel_X'], p['Pixel_Y']))

                    srs = osr.SpatialReference()
                    srs.ImportFromEPSG(4326)

                    ds = gdal.Open(img_path)
                    gdal.Translate(temp_vrt, ds, GCPs=gcps, outputSRS=srs.ExportToWkt())
                    gdal.Warp(output_tif, temp_vrt, options=gdal.WarpOptions(polynomialOrder=1, dstSRS='EPSG:4326'))
                    
                    st.success("🎉 Đã tạo file GeoTIFF thành công!")
                    
                    with open(output_tif, "rb") as file:
                        st.download_button(
                            label="📥 TẢI XUỐNG BẢN ĐỘ (.TIF)",
                            data=file,
                            file_name="so_do_luoi_dien.tif",
                            mime="image/tiff",
                            type="primary"
                        )
            except Exception as e:
                st.error(f"Lỗi khi xử lý: {e}")
    elif uploaded_file:
        st.warning(f"Cần ít nhất 3 điểm mốc để xuất file (Hiện tại: {len(st.session_state['gcp_list'])}/3).")
