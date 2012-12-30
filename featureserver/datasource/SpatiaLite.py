'''
Created on Oct 22, 2012
    
@author: michel
'''

import os

from DataSource import DataSource
from vectorformats.feature import Feature
from vectorformats.formats.wkt import WKT

from ..parsers.WebFeatureService.Response.InsertResult import InsertResult
from ..parsers.WebFeatureService.Response.UpdateResult import UpdateResult
from ..parsers.WebFeatureService.Response.DeleteResult import DeleteResult
from ..parsers.WebFeatureService.Response.ReplaceResult import ReplaceResult

from ..exceptions.syntax import SyntaxException
from ..exceptions.datasource import ConnectionException

from pyspatialite import dbapi2 as db

import datetime



class SpatiaLite (DataSource):
    
    _query_actions  = { 'eq' : '=', 'neq' : '!=',
                        'lt': '<', 'gt': '>',
                        'ilike' : 'ilike', 'like' : 'like',
                        'gte': '>=', 'lte': '<=' }

    def __init__(self, name, file, fid = "gid", geometry = "the_geom", fe_attributes = 'true', srid = 4326, srid_out = 4326, encoding = "utf-8", writable = True, attribute_cols = "*", **kwargs):
        DataSource.__init__(self, name, **kwargs)
        self.file           = file
        self.table          = kwargs["layer"]
        self.fid_col        = fid
        self.geom_col       = geometry
        self.srid           = srid
        self.srid_out       = srid_out
        self.writable       = writable
        self.attribute_cols = attribute_cols
        self.encoding       = encoding
        
        self._connection    = None

        self.fe_attributes = True
        if fe_attributes.lower() == 'false':
            self.fe_attributes  = False


    def begin(self):
        if not os.path.exists(self.file):
            raise ConnectionException(**{'layer':self.name,'locator':'SpatialLite'})
        self._connection = db.connect(self.file, check_same_thread = False)
    
    def close(self):
        if self._connection:
            self._connection.close()

    def commit(self):
        if self.writable:
            self._connection.commit()
        self.close()

    def rollback(self):
        if self.writable and self._connection:
            self._connection.rollback()
        self.close()

    def insert(self, action):
        sql = action.statement
        
        cursor = self._connection.cursor()
        try:
            cursor.execute(str(sql))
        except Exception as e:
            raise SyntaxException(locator = self.__class__.__name__, dump = str(e))
        
        cursor.execute("SELECT last_insert_rowid()")
        id =  cursor.fetchone()[0]
        
        result = InsertResult("")
        result.add(id)
                
        return result
            

    def update(self, action):
        sql = action.statement
        
        cursor = self._connection.cursor()
        try:
            cursor.execute(str(sql))
        except Exception as e:
            raise SyntaxException(locator = self.__class__.__name__, dump = str(e))
        
        result = UpdateResult("")
        result.extend(action.ids)
        
        return result


    def delete(self, action):
        sql = action.statement
        
        cursor = self._connection.cursor()

        try:
            cursor.execute(str(sql))
        except Exception as e:
            raise SyntaxException(locator = self.__class__.__name__, dump = str(e))
        
        result = DeleteResult("")
        result.extend(action.ids)
        
        return result
        

    def select(self, action):
        cursor = self._connection.cursor()
        
        sql = "SELECT AsText(Transform(%s, %d)) as fs_text_geom, " % (self.getGeometry(), int(self.srid_out))
        
        
        # add attributes from config file
        if hasattr(self, 'version'):
            sql += "%s as version, " % self.version
        if hasattr(self, 'ele'):
            sql += "%s as ele, " % self.ele
            
        sql += "\"%s\"" % self.fid_col
        
        if len(self.attribute_cols) > 0:
            sql += ", %s" % self.attribute_cols
            
        if hasattr(self, "additional_cols") and len(self.additional_cols) > 0:
            cols = self.additional_cols.split(';')
            additional_col = ",".join(cols)
            sql += ", %s" % additional_col
        
        # add attributes from parser
        if self.fe_attributes:
            if action.attributes is not None and len(action.attributes) > 0:
                ad_cols = self.getColumns()
                # removes attributes that already are defined in the configuration file
                fe_cols = filter(lambda x: x not in ad_cols, action.attributes)
            
                if len(fe_cols) > 0:
                    sql += ", %s" % ",".join(fe_cols)

        sql += " FROM \"%s\"" % (self.table)
        
        
        if action.statement is not None:
            sql += " WHERE " + action.statement
        
        from pprint import pprint
        pprint(action.constraints)
        pprint(action.sort)
        
        if action.constraints.has_key('order_by'):
            sql += " ORDER BY " + action.constraints['order_by']
            if action.constraints.has_key('order') and action.constraints['order'].upper() in ['ASC', 'DESC']:
                sql += " " + action.constraints['order'].upper()

        print sql
        
        try:
            cursor.execute(str(sql))
        except Exception as e:
            raise SyntaxException(locator = self.__class__.__name__, layer=self.layer, dump = str(e))

        result = cursor.fetchall()

                
        columns = [desc[0] for desc in cursor.description]
        features = []
        
        for row in result:
            props = dict(zip(columns, row))
            if not props['fs_text_geom']: continue
            geom  = WKT.from_wkt(props['fs_text_geom'])
            id = props[self.fid_col]
            del props[self.fid_col]
            if self.attribute_cols == '*':
                del props[self.getGeometry()]
            del props['fs_text_geom']
            for key, value in props.items():
                if isinstance(value, str):
                    props[key] = unicode(value, self.encoding)
                elif isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
                    # stringify datetimes
                    props[key] = str(value)

                try:
                    if isinstance(value, decimal.Decimal):
                        props[key] = unicode(str(value), self.encoding)
                except:
                    pass

            if (geom):
                features.append( Feature( layer=action.layer, id=id, geometry=geom, geometry_attr=self.getGeometry(), srs=self.srid_out, props=props ) )
        
        return features
    
    
    def getColumns(self):
        cols = []

        if hasattr(self, 'attribute_cols'):
            cols = self.attribute_cols.split(",")
        
        cols.append(self.getGeometry())
        cols.append(self.fid_col)
        
        if hasattr(self, 'version'):
            cols.append(self.version)
        if hasattr(self, 'ele'):
            cols.append(self.ele)
        
        return cols
    
    def getGeometry(self):
        return self.geom_col
    def getAttributes(self):
        return self.attribute_cols
        
    
    def getAttributeDescription(self, attribute):
        self.begin()
        cursor = self._connection.cursor()
        result = []
        
        sql = "PRAGMA table_info(%s)"
        
        try:
            cursor.execute(sql % self.table)
            result = cursor.fetchall()
            self.commit()
        except: pass
    
        type = 'string'
        length = ''
        
        if len(result) > 0:
            for col in result:
                if col[1] == attribute:
                    if str(col[2]).lower().startswith('int'):
                        type = 'integer'
                        length = ''
                        break
    
        return (type, length)
