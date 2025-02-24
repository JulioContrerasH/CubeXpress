from __future__ import annotations

from typing import List, Set, TypeAlias, Final
from typing_extensions import TypedDict

import pandas as pd
from pydantic import BaseModel, field_validator, model_validator, model_validator
from pyproj import CRS

# Type definitions
NumberType: TypeAlias = int | float

# Constants for required keys in the geotransform
REQUIRED_KEYS: Final[Set[str]] = {
    'scaleX', 'shearX', 'translateX',
    'scaleY', 'shearY', 'translateY'
}

class GeotransformDict(TypedDict):
    """
    Type definition for a geotransform dictionary containing spatial transformation parameters.
    
    Attributes:
        scaleX (NumberType): The scaling factor in the X direction.
        shearX (NumberType): The shear factor in the X direction.
        translateX (NumberType): The translation in the X direction.
        scaleY (NumberType): The scaling factor in the Y direction.
        shearY (NumberType): The shear factor in the Y direction.
        translateY (NumberType): The translation in the Y direction.
    """
    scaleX: NumberType
    shearX: NumberType
    translateX: NumberType
    scaleY: NumberType
    shearY: NumberType
    translateY: NumberType


class RasterTransform(BaseModel):
    """
    Represents a single geospatial metadata entry with CRS and transformation information.
    
    Attributes:
        id (str): The unique identifier for the raster metadata.
        crs (str): The Coordinate Reference System string (EPSG code or WKT).
        geotransform (GeotransformDict): A dictionary containing spatial transformation parameters.
        width (int): Raster width in pixels.
        height (int): Raster height in pixels.
    
    Example:
        >>> metadata = RasterTransform(
        ...     id="image1",
        ...     crs="EPSG:4326",
        ...     geotransform={
        ...         'scaleX': 1.0, 'shearX': 0, 'translateX': 100.0,
        ...         'scaleY': 1.0, 'shearY': 0, 'translateY': 200.0
        ...     },
        ...     width=1000,
        ...     height=1000
        ... )
        RasterTransform(crs='EPSG:4326', width=1000, height=1000)
    """
    id: str
    crs: str
    geotransform: GeotransformDict
    width: int
    height: int
    
    @model_validator(mode="before")
    def validate_geotransform(cls, values):
        """
        Validates the geotransform dictionary to ensure it has the required keys 
        and that all values are numeric and non-zero where applicable.

        Args:
            values (dict): The input values being validated.

        Returns:
            dict: The validated values.

        Raises:
            ValueError: If validation fails for missing keys, invalid types, or zero scale values.
        """
        geotransform = values.get('geotransform')
        
        if not isinstance(geotransform, dict):
            raise ValueError(f"Expected geotransform to be a dictionary, got {type(geotransform)}")
        
        missing_keys = REQUIRED_KEYS - set(geotransform.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys: {missing_keys}")
        
        extra_keys = set(geotransform.keys()) - REQUIRED_KEYS
        if extra_keys:
            raise ValueError(f"Unexpected keys found: {extra_keys}")

        for key in REQUIRED_KEYS:
            if not isinstance(geotransform[key], (int, float)):
                raise ValueError(f"Value for '{key}' must be numeric (int or float)")

        if not (geotransform['scaleX'] and geotransform['scaleY']):
            raise ValueError("Scale values cannot be zero")

        return values
    
    @field_validator('width', 'height')
    @classmethod
    def validate_positive(cls, value: int, field) -> int:
        """
        Validates that width and height are positive integers.

        Args:
            value (int): The value of width or height to validate.
            field: The field being validated (width or height).

        Returns:
            int: The validated value.

        Raises:
            ValueError: If the value is not positive.
        """
        if value <= 0:
            raise ValueError(f"{field.field_name} must be positive and greater than zero, but got {value}")
        return value

    def __str__(self) -> str:
        """
        Provides a string representation of the RasterTransform instance with a table 
        format for the geotransform parameters.

        Returns:
            str: A formatted string showing the raster metadata and geotransform.
        """
        geotransform_data = {
            'Parameter': ['scaleX', 'shearX', 'translateX', 'scaleY', 'shearY', 'translateY'],
            'Value': [
                self.geotransform["scaleX"], self.geotransform["shearX"], self.geotransform["translateX"],
                self.geotransform["scaleY"], self.geotransform["shearY"], self.geotransform["translateY"]
            ]
        }
        geotransform_df = pd.DataFrame(geotransform_data)
        return f"RasterTransform(crs={self.crs}, width={self.width}, height={self.height})\n\nGeotransform:\n{geotransform_df}"

class RasterTransformSet(BaseModel):
    """
    Container for multiple RasterTransform instances with bulk validation capabilities.
    
    Attributes:
        rastertransformset (List[RasterTransform]): A list of RasterTransform metadata entries.
    
    Example:
        >>> metadatas = RasterTransformSet(rastertransformset=[metadata1, metadata2])
        >>> df = metadatas.export_df()
    """
    rastertransformset: List[RasterTransform]
    
    @model_validator(mode="after")
    def validate_crs(self) -> RasterTransformSet:
        """
        Validates that all entries have consistent and valid CRS formats.

        Returns:
            RasterTransformSet: The validated instance.

        Raises:
            ValueError: If any CRS is invalid or inconsistent.
        """
        crs_set: Set[str] = {meta.crs for meta in self.rastertransformset}
        validated_crs: Set[str] = set()
        
        # Validate CRS formats
        for crs in crs_set:
            if crs not in validated_crs:
                try:
                    CRS.from_string(crs)
                    validated_crs.add(crs)
                except Exception as e:
                    raise ValueError(f"Invalid CRS format: {crs}") from e
        
        # Validate ids, they must be unique
        ids = {meta.id for meta in self.rastertransformset}
        if len(ids) != len(self.rastertransformset):
            raise ValueError("All entries must have unique IDs")

        return self
    
    def export_df(self) -> pd.DataFrame:
        """
        Exports the raster metadata to a pandas DataFrame.

        Returns:
            pd.DataFrame: A DataFrame containing the metadata for all entries.
        
        Example:
            >>> df = raster_transform_set.export_df()
            >>> print(df)
        """
        return pd.DataFrame([
            {   
                'id': meta.id,
                'x': meta.geotransform['translateX'],
                'y': meta.geotransform['translateY'],
                'crs': meta.crs,
                'width': meta.width,
                'height': meta.height,
                'geotransform': meta.geotransform
            }
            for meta in self.rastertransformset
        ])
    
    def __str__(self) -> str:
        """
        Provides a string representation of the metadata set including a table of all entries.

        Returns:
            str: A string representation of the entire RasterTransformSet.
        """
        df = self.export_df()
        num_entries = len(self.rastertransformset)
        return f"RasterTransformSet({num_entries} entries)\n\n{df}"