import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image
import os
from osgeo import gdal, osr

st.set_page_config(page_title="Tool Georeferencing Lưới Điện", layout="wide")
st.title("📍 Ứng dụng Nắn chỉnh ảnh sơ đồ sang GeoTIFF")

# 1. Tải ảnh lên
uploaded_file = st.sidebar.file_uploader("Bước 1: Tải lên ảnh sơ đồ (JPG/PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file:
    img = Image.open(uploaded_file)
    img_path = "input_temp.jpg"
    img.save(img_path)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Chọn điểm mốc trên ảnh")
        # Hiển thị ảnh và lấy tọa độ pixel khi click
        value = streamlit_image_coordinates(img, key="pill")
        
        if value:
            st.info(f"Tọa độ Pixel vừa chọn: X={value['x']}, Y={value['y']}")
            # Lưu tạm tọa độ pixel vào session state
            st.session_state['last_pixel'] = (value['x'], value['y'])

    with col2:
        st.subheader("Nhập tọa độ WGS84 tương ứng")
        
        if 'gcp_list' not in st.session_state:
            st.session_state['gcp_list'] = []

        with st.form("add_gcp_form"):
            lat = st.number_input("Kinh độ (Longitude / X)", format="%.6f")
            lon = st.number_input("Vĩ độ (Latitude / Y)", format="%.6f")
            add_button = st.form_submit_button("Thêm điểm mốc (GCP)")

            if add_button and 'last_pixel' in st.session_state:
                px, py = st.session_state['last_pixel']
                st.session_state['gcp_list'].append({
                    'px': px, 'py': py, 'lat': lat, 'lon': lon
                })
                st.success(f"Đã thêm điểm mốc thứ {len(st.session_state['gcp_list'])}")

        # Hiển thị danh sách các điểm đã chọn
        if st.session_state['gcp_list']:
            st.write("Danh sách điểm mốc hiện có:")
            st.table(st.session_state['gcp_list'])
            
            if st.button("Xóa danh sách điểm"):
                st.session_state['gcp_list'] = []
                st.rerun()

    # 2. Xử lý xuất file TIF
    if len(st.session_state['gcp_list']) >= 3:
        if st.button("🚀 XUẤT FILE GEOTIFF", type="primary"):
            try:
                output_tif = "output_map.tif"
                temp_vrt = "temp.vrt"

                # Tạo danh sách GCPs cho GDAL
                gcps = []
                for p in st.session_state['gcp_list']:
                    # Cú pháp: gdal.GCP(X_thực, Y_thực, Z, X_pixel, Y_pixel)
                    gcps.append(gdal.GCP(p['lat'], p['lon'], 0, p['px'], p['py']))

                # Thiết lập SRS (WGS84 = EPSG:4326)
                srs = osr.SpatialReference()
                srs.ImportFromEPSG(4326)

                # Bước A: Gắn GCP vào file ảo VRT
                ds = gdal.Open(img_path)
                gdal.Translate(temp_vrt, ds, GCPs=gcps, outputSRS=srs.ExportToWkt())

                # Bước B: Nắn ảnh (Warp) sang file TIF thực tế
                # Sử dụng Polynomial bậc 1 cho 3-4 điểm
                gdal.Warp(output_tif, temp_vrt, options=gdal.WarpOptions(polynomialOrder=1, dstSRS='EPSG:4326'))
                
                st.success("Đã tạo file GeoTIFF thành công!")
                
                with open(output_tif, "rb") as file:
                    st.download_button(
                        label="📥 Tải xuống file .TIF",
                        data=file,
                        file_name="so_do_luoi_dien.tif",
                        mime="image/tiff"
                    )
            except Exception as e:
                st.error(f"Lỗi khi xử lý: {e}")
    else:
        st.warning("Cần ít nhất 3 điểm mốc để có thể nắn ảnh.")