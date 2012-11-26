
from WFS import WFS
from FeatureServer.Exceptions.MissingParameterException import MissingParameterException
from FeatureServer.Parsers.WFS_V1_Parser import WFS_V1_Parser

class WFS_V1(WFS):
    ''' implements WFS version 1.1.0 specification '''

    # TODO: check if attrib exists on node
    def find_typenames(self):
        
        # check POST data
        if self.request.post_xml is not None:
            # check if child nodes <wfs:TypeName> exists of <wfs:DescribeFeatureType/>
            typenames = self.request.post_xml.xpath("/*[local-name() = 'DescribeFeatureType']/*[local-name() = 'TypeName']")
            if len(typenames) > 0:
                for typename in typenames:
                    self.datasources.update({str(typename.text) : []})
                return
            
            # check if child nodes <wfs:Query typeName=""/> exists
            typenames = self.request.post_xml.xpath("/*[local-name() = 'GetFeature']/*[local-name() = 'Query']")
            if len(typenames) > 0:
                for typename in typenames:
                    self.datasources.update({typename.attrib['typeName'] : []})
                return
            
            # find typenames in <wfs:Transaction/>
            #    - <wfs:Insert><typeName/></wfs:Insert> (typenames are named child nodes)
            inserts = self.request.post_xml.xpath("/*[local-name() = 'Transaction']/*[local-name() = 'Insert']")
            for insert in inserts:
                self.datasources.update({ str(key.xpath("local-name()")) : [] for key in insert.iterchildren() })
            #    - <wfs:Update typeName=""/>
            #    - <wfs:Delete typeName=""/>
            nodes = self.request.post_xml.xpath("/*[local-name() = 'Transaction']/*[local-name() = 'Update' or local-name() = 'Delete']")
            if len(nodes) > 0:
                self.datasources.update({ str(node.attrib['typeName']) : [] for node in nodes })
                return
        
        # check GET data
        if self.request.params.has_key('typename'):
            self.datasources.update({key : [] for key in self.request.params['typename'].split(",")})
            return
        
        raise MissingParameterException(locator = "Service/" + self.__class__.__name__, parameter = "typeName")

    def create_parser(self):
        return WFS_V1_Parser(self)

