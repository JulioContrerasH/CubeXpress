# Functions in **CubeXpress**

This section explores how the **[CubeXpress](https://pypi.org/project/cubexpress/)** package streamlines working with satellite imagery and geospatial data in Google Earth Engine (GEE). **CubeXpress** provides a simple, unified API for creating download requests, handling automatic tiling of large images, and performing pixel-level computations.

---

## **1. Introduction to `cubexpress`**

The **CubeXpress** package is designed to simplify and accelerate the retrieval and processing of large geospatial datasets from Google Earth Engine (GEE). Key capabilities include:

- **Unified “Request” and “RequestSet” model:**  
  Define one or many image download requests with minimal code, then process them in bulk.

- **Automatic sub-tiling:**  
  If an image exceeds GEE’s size limits, CubeXpress will automatically split (“quad-split”) the request into smaller tiles until it succeeds.

- **Parallel downloads:**  
  Multiple images can be retrieved concurrently using the `nworkers` parameter, greatly improving performance.

- **Flexible inputs:**  
  - Pass an `ee.Image` object (including complex expressions like `.normalizedDifference(...)` or `.divide(...)`).  
  - Or simply provide a string with the asset ID (e.g., `"COPERNICUS/S2_SR_HARMONIZED/..."`).  

---

## **2. Main Classes and Functions**

### **`Request`**
A single image download specification.

- **Parameters**:  
  - `id`: Unique identifier for the request (used for naming output files).  
  - `raster_transform`: Spatial metadata, typically created via `lonlat2rt(...)`.  
  - `image`: Can be an `ee.Image` (serialized internally) or a string asset ID.  
  - `bands`: List of band names to extract.  

- **Example**:

  ```python
  request = cubexpress.Request(
      id="my_image",
      raster_transform=geotransform,
      bands=["B4", "B3", "B2"],
      image="COPERNICUS/S2_SR_HARMONIZED/20240105T..."
  )
  ```

### **`RequestSet`**
A collection of `Request` objects, validated and prepared for download.  

- **Creates** an internal **DataFrame** with all request details (the “manifest”). 

- **Example**:
  ```python
  requests = [request1, request2, ...]
  request_set = cubexpress.RequestSet(requestset=requests)
  ```

### **`getcube()`**
The main download function. It reads the manifest from a `RequestSet`, calls GEE’s internal APIs (`getPixels`/`computePixels`), and writes GeoTIFFs to disk.  

- **Arguments**:
  - `request`: The `RequestSet` to process.
  - `output_path`: Directory for saving the resulting GeoTIFF files.
  - `nworkers`: Number of parallel threads (workers).
  - `max_deep_level`: Maximum recursion depth if sub-tiling is required.

- **Returns**: A list of `pathlib.Path` objects pointing to the downloaded files.
