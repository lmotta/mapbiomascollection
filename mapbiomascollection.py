# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : MapBiomas Collection
Description          : This plugin lets you get collection of mapping from MapBiomas Project(http://mapbiomas.org/).
Date                 : August, 2020
copyright            : (C) 2019 by Luiz Motta, Updated by Luiz Cortinhas (2020)
email                : motta.luiz@gmail.com, luiz.cortinhas@solved.eco.br

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, time, json
import urllib.parse
import warnings
from osgeo import gdal

from qgis.PyQt.QtCore import (
    Qt, QSettings, QLocale,
    QObject, pyqtSlot, pyqtSignal
)
from qgis.PyQt.QtWidgets import (
    QWidget, QPushButton,
    QSlider, QLabel,
    QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QHBoxLayout
)
from qgis.PyQt.QtGui import (
    QColor, QPixmap, QIcon
)

from qgis.core import (
    QgsApplication, Qgis, QgsProject,
    QgsRasterLayer,
    QgsTask
)
from qgis.gui import QgsGui, QgsMessageBar, QgsLayerTreeEmbeddedWidgetProvider
#https://production.mapserver.mapbiomas.org/wms/coverage.map?service=WMS&request=GetMap&layers=coverage&styles=&format=image%2Fpng&transparent=true&version=1.3.0&territory_ids=96&year=2019&class_tree_node_ids=28%2C36%2C50%2C51%2C52%2C35%2C29%2C37%2C38%2C41%2C40%2C39%2C30%2C43%2C42%2C54%2C56%2C55%2C57%2C53%2C44%2C31%2C45%2C46%2C47%2C34%2C32%2C49%2C48%2C33&width=256&height=256&srs=EPSG%3A3857&maxZoom=19&minZoom=4&bbox=-5635549.221409475,-1252344.2714243263,-5009377.085697311,-626172.1357121632

class MapBiomasCollectionWidget(QWidget):
    classRef = {1:{'color':'129912','parent':0,'status':False},
				2:{'color':'1F4423','parent':1,'status':False},
				3:{'color':'006400','parent':2,'status':False},
				4:{'color':'32CD32','parent':2,'status':False},
				5:{'color':'687537','parent':2,'status':False},
				6:{'color':'000000','parent':0,'status':False},
				7:{'color':'000000','parent':0,'status':False},
				8:{'color':'000000','parent':0,'status':False},
				9:{'color':'935132','parent':1,'status':False},
				10:{'color':'BBFCAC','parent':0,'status':False},
				11:{'color':'45C2A5','parent':10,'status':False},
				12:{'color':'B8AF4F','parent':10,'status':False},
				13:{'color':'BDB76B','parent':10,'status':False},
				14:{'color':'FFFFB2','parent':0,'status':False},
				15:{'color':'FFD966','parent':14,'status':False},
				16:{'color':'000000','parent':0,'status':False},
				17:{'color':'000000','parent':0,'status':False},
				18:{'color':'E974ED','parent':14,'status':False},
				19:{'color':'D5A6BD','parent':18,'status':False},
				20:{'color':'C27BA0','parent':19,'status':False},
				21:{'color':'FFEFC3','parent':14,'status':False},
				22:{'color':'EA9999','parent':0,'status':False},
				23:{'color':'DD7E6B','parent':22,'status':False},
				24:{'color':'af2a2a','parent':22,'status':False},
				25:{'color':'FF99FF','parent':22,'status':False},
				26:{'color':'0000FF','parent':0,'status':False},
				27:{'color':'D5D5E5','parent':0,'status':False},
				28:{'color': '000000','parent':0,'status':False},
				29:{'color':'FF8C00','parent':10,'status':False},
				30:{'color':'8A2BE2','parent':22,'status':False},
				31:{'color':'29EEE4','parent':26,'status':False},
				32:{'color':'968c46','parent':10,'status':False},
				33:{'color':'0000FF','parent':26,'status':False},
				34:{'color':'000000','parent':0,'status':False},
				35:{'color':'000000','parent':0,'status':False},
				36:{'color':'f3b4f1','parent':18,'status':False},
				37:{'color':'000000','parent':0,'status':False},
				38:{'color':'000000','parent':0,'status':False},
				39:{'color':'c59ff4','parent':19,'status':False},
				40:{'color':'000000','parent':0,'status':False},
				41:{'color':'e787f8','parent':19,'status':False}}
    @staticmethod
    def getParentColor(item):
        if item['parent'] == 0 and item['status'] == False:
            return 'FFFFFF'
        if item['status']:
            return item['color']
        else:
            return MapBiomasCollectionWidget.getParentColor(MapBiomasCollectionWidget.classRef[item['parent']])

    @staticmethod
    def getUrl(url, version, year, l_class_id):
        l_strClass = [ str(item) for item in l_class_id ]
        for item in MapBiomasCollectionWidget.classRef.keys():
            MapBiomasCollectionWidget.classRef[item]['status'] = False
        for item in l_class_id:
            MapBiomasCollectionWidget.classRef[item]['status'] = True
        #ENV Percorredor!
        env = 'env='
        for item in MapBiomasCollectionWidget.classRef.keys():
            classID = item
            color = MapBiomasCollectionWidget.getParentColor(MapBiomasCollectionWidget.classRef[item])
            env = env + f'{classID}:{color};'
        #env=1:00FF00;2:triangle;3:12
        #crs=EPSG:3857&dpiMode=7&format=image/png&layers=mapbiomas&styles&url=http://azure.solved.eco.br:8080/geoserver/solved/wms
        params = {
            'IgnoreGetFeatureInfoUrl': '1',
            'IgnoreGetMapUrl': '1',
            'service': 'WMS',
            'styles': 'solved:mapbiomas_legend',
            'styles': '',
            'request': 'GetMap',
            'format': 'image/png', # image/png8
            'layers': f"mapbiomas_{year}",
            'crs': 'EPSG:4326'
        }
        paramsWms = '&'.join( [ f"{k}={v}" for k,v in params.items() ] )
        #'IgnoreGetFeatureInfoUrl=1&IgnoreGetMapUrl=1&crs=EPSG:3857&dpiMode=7&format=image/png&layers=coverage&styles='
        paramsQuote = f""
        paramsQuote = f"{paramsQuote}&transparent=true&version=1.1.1"
        paramsQuote = urllib.parse.quote( f"{paramsQuote}&exceptions=application/vnd.ogc.se_inimage&years={year}&{env}&classification_ids=" )# a ordem importa
        paramClassification = ','.join( l_strClass )
        msg = f"{paramsWms}&url={url}?{paramsQuote}{paramClassification}"
        #warnings.warn(msg)
        return f"{paramsWms}&url={url}?{paramsQuote}{paramClassification}"

    def __init__(self, layer, data):
        def getYearClasses():
            def getYear():
                values = [ item for item in paramsSource if item.find('years=') > -1]
                return self.maxYear if not len( values ) == 1 else int( values[0].split('=')[1] )

            def getClasses():
                values = [ item for item in paramsSource if item.find('classification_ids=') > -1 ]
                #warnings.warn(str(values))
                if (not len( values ) == 1) or (values[0] == 'classification_ids='):
                    return [] 
                else :
                    return [ int( item ) for item in values[0].split('=')[1].split(',') ]

            paramsSource = urllib.parse.unquote( self.layer.source() ).split('&')
            return getYear(), getClasses()

        def setGui(classes):
            def createLayoutYear():
                lytYear = QHBoxLayout()
                lblTitleYear = QLabel( 'Year:', self )
                lblYear = QLabel( str( self.year ), self )
                lytYear.addWidget( lblTitleYear  )
                lytYear.addWidget( lblYear )
                return lytYear, lblYear

            def createLayoutSlider():
                def createButtonLimit(limitYear, sFormat, objectName):
                    label = sFormat.format( limitYear )
                    pb = QPushButton( label, self )
                    width = pb.fontMetrics().boundingRect( label ).width() + 7
                    pb.setMaximumWidth( width )
                    pb.setObjectName( objectName )
                    return pb

                def createSlider():
                    slider = QSlider( Qt.Horizontal, self )
                    #slider.setTracking( False ) # Value changed only released mouse
                    slider.setMinimum( self.minYear )
                    slider.setMaximum( self.maxYear )
                    slider.setSingleStep(1)
                    slider.setValue( self.year )
                    interval = int( ( self.maxYear - self.minYear) / 10 )
                    slider.setTickInterval( interval )
                    slider.setPageStep( interval)
                    slider.setTickPosition( QSlider.TicksBelow )
                    return slider

                lytSlider = QHBoxLayout()
                pbMin = createButtonLimit( self.minYear, "{} <<", 'minYear' )
                lytSlider.addWidget( pbMin )
                slider = createSlider()
                lytSlider.addWidget( slider )
                pbMax = createButtonLimit( self.maxYear, ">> {}", 'maxYear' )
                lytSlider.addWidget( pbMax )
                return lytSlider, slider, pbMin, pbMax

            def createTree(classes):
                def populateTreeJson(classes, itemRoot):
                    def createIcon(color):
                        color = QColor( color['r'], color['g'], color['b'] )
                        pix = QPixmap(16, 16)
                        pix.fill( color )
                        return QIcon( pix )

                    def createItem(itemRoot, name, class_id, flags, icon):
                        # WidgetItem
                        item = QTreeWidgetItem( itemRoot )
                        item.setText(0, name )
                        item.setData(0, Qt.UserRole, class_id )
                        checkState = Qt.Checked if class_id in self.l_class_id else Qt.Unchecked
                        item.setCheckState(0, checkState )
                        item.setFlags( flags )
                        item.setIcon(0, icon )
                        return item

                    flags = itemRoot.flags() | Qt.ItemIsUserCheckable
                    for k in classes:
                        class_id = classes[ k ]['id']
                        icon = createIcon( classes[ k ]['color'] )
                        itemClass = createItem( itemRoot, k, class_id, flags, icon )
                        if 'classes' in classes[ k ]:
                            populateTreeJson( classes[ k ]['classes'], itemClass )

                tree = QTreeWidget( self )
                tree.setSelectionMode( tree.NoSelection )
                tree.setHeaderHidden( True )
                itemRoot = QTreeWidgetItem( tree )
                itemRoot.setText(0, 'Classes')
                populateTreeJson( classes, itemRoot )
                return tree, itemRoot

            lytYear, lblYear  = createLayoutYear()
            lytSlider, slider, pbMin, pbMax = createLayoutSlider( )
            tree, itemClasses = createTree( classes )
            itemClasses.setExpanded( True )
            # Layout
            lyt = QVBoxLayout()
            lyt.addLayout( lytYear )
            lyt.addLayout( lytSlider )
            lyt.addWidget( tree )
            msgBar = QgsMessageBar(self)
            lyt.addWidget( msgBar )
            self.setLayout( lyt )


            return {
                'msgBar': msgBar,
                'lblYear': lblYear,
                'slider': slider,
                'pbMin': pbMin,
                'pbMax': pbMax,
                'tree': tree,
                'itemClasses': itemClasses
            }

        super().__init__()
        self.layer = layer
        self.version = data['version']
        self.url = data['url']
        self.minYear = data['years']['min']
        self.maxYear = data['years']['max']

        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()

        self.year, self.l_class_id = getYearClasses() # Depend self.maxYear
        self.valueYearLayer = self.year

        r = setGui( data['classes'] )
        self.msgBar = r['msgBar']
        self.lblYear = r['lblYear']
        self.slider = r['slider']
        self.pbMin = r['pbMin']
        self.pbMax = r['pbMax']
        self.tree = r['tree']
        self.itemClasses = r['itemClasses']

        # Connections
        self.slider.valueChanged.connect( self.on_yearChanged )
        self.slider.sliderReleased.connect( self.on_released )
        self.pbMin.clicked.connect( self.on_limitYear )
        self.pbMax.clicked.connect( self.on_limitYear )
        self.tree.itemChanged.connect( self.on_classChanged )

    def _uploadSource(self):
        def checkDataSource():
            url = self.getUrl( self.url, self.version, self.year, self.l_class_id )
            print('URL:')
            print(url)
            name = f"Collection {self.version} - {self.year}"
            print('name:')
            print(name)
            args = [ url, name, self.layer.providerType() ]
            layer = QgsRasterLayer( *args )
            if not layer.isValid():
                msg = f"Error server {self.url}"
                return { 'isOk': False, 'message': msg }
            args += [ self.layer.dataProvider().ProviderOptions() ]
            return { 'isOk': True, 'args': args }

        self.setEnabled( False )
        r = checkDataSource()
        if not r['isOk']:
            self.msgBar.pushMessage( r['message'], Qgis.Critical, 4 )
            self.setEnabled( True )
            return
        self.layer.setDataSource( *r['args'] ) # The Widget will be create agai

    @pyqtSlot()
    def on_released(self):
        if self.valueYearLayer == self.year:
            return

        self._uploadSource()

    @pyqtSlot(int)
    def on_yearChanged(self, value):
        if value == self.year:
            return

        self.yearChanged = True
        self.year = value
        self.lblYear.setText( str( value ) )
        if not self.slider.isSliderDown(): # Keyboard
            self.valueYearLayer = self.year
            self._uploadSource()

    @pyqtSlot(bool)
    def on_limitYear(self, checked):
        year = self.maxYear if self.sender().objectName() == 'maxYear' else self.minYear
        if year == self.year:
            return

        self.year = year
        self.lblYear.setText( str( self.year ) )
        self.valueYearLayer = self.year
        self._uploadSource()

    @pyqtSlot(QTreeWidgetItem, int)
    def on_classChanged(self, item, column):
        value = item.data( column, Qt.UserRole)
        color = item.data( column, Qt.UserRole)
        status = item.checkState( column ) == Qt.Checked
        f = self.l_class_id.append if status else self.l_class_id.remove
        f( value )
        self._uploadSource()


class LayerMapBiomasCollectionWidgetProvider(QgsLayerTreeEmbeddedWidgetProvider):
    def __init__(self, data):
        super().__init__()
        self.data = data

    def id(self):
        return 'mapbiomascollection'

    def name(self):
        return "Layer MapBiomas Collection"

    def createWidget(self, layer, widgetIndex):
        return MapBiomasCollectionWidget( layer, self.data )

    def supportsLayer(self, layer):
        if not layer.providerType() == 'wms':
            return False
        source = urllib.parse.unquote( layer.source() ).split('&')
        print('Here')
        host = f"url={self.data['url']}?map=wms/v/{self.data['version']}/classification/coverage.map"
        print(host)
        #warnings.warn(host)
        l_url = [ item for item in source if item.find( host ) > -1 ]
        return len( l_url ) > 0


class MapBiomasCollection(QObject):
    MODULE = 'MapBiomasCollection'
    def __init__(self, iface):
        def getConfig():
            def existLocaleConfig():
                overrideLocale = QSettings().value('locale/overrideFlag', False, type=bool)
                locale = QLocale.system().name() if not overrideLocale else QSettings().value('locale/userLocale', '')
                name = f_name.format( locale=locale )
                fileConfig = os.path.join( dirname, name )
                if os.path.exists( fileConfig ):
                    return { 'isOk': True, 'fileConfig': fileConfig }
                return { 'isOk': False }

            f_name = "mapbiomascollection_{locale}.json"
            dirname = os.path.dirname(__file__)
            r = existLocaleConfig()
            if r['isOk']:
                fileConfig = r['fileConfig']
            else:
                name = f_name.format( locale='en_US')
                fileConfig = os.path.join( dirname, name )

            with open(fileConfig, encoding='utf-8') as json_file:
                data = json.load(json_file)    
            return data

        super().__init__()        
        self.msgBar = iface.messageBar()
        self.root = QgsProject.instance().layerTreeRoot()
        self.taskManager = QgsApplication.taskManager()
        self.data = getConfig()
        self.widgetProvider = None

    def register(self):
        self.widgetProvider = LayerMapBiomasCollectionWidgetProvider( self.data )
        registry = QgsGui.layerTreeEmbeddedWidgetRegistry()
        if not registry.provider( self.widgetProvider.id() ) is None:
            registry.removeProvider( self.widgetProvider.id() )
        registry.addProvider( self.widgetProvider )

    def run(self):
        def createLayer(task, year, l_class_id):
            args = ( self.data['url'], self.data['version'], year, l_class_id )
            #warnings.warn( self.data['url'])
            url = MapBiomasCollectionWidget.getUrl( *args )
            #warnings.warn(url)
            return ( url, f"Collection {self.data['version']} - {year}", 'wms' )

        def finished(exception, result=None):
            self.msgBar.clearWidgets()
            if not exception is None:
                msg = f"Error: Exception: {exception}"
                self.msgBar.pushMessage( self.MODULE, msg, Qgis.Critical, 4 )
                return
            layer = QgsRasterLayer( *result )
            if not layer.isValid():
                source = urllib.parse.unquote( layer.source() ).split('&')
                url = [ v for v in source if v.split('=')[0] == 'url' ][0]
                msg = f"!!!Error server: Get {url}"
                self.msgBar.pushCritical( self.MODULE, msg )
                return

            project = QgsProject.instance()
            totalEW = int( layer.customProperty('embeddedWidgets/count', 0) )
            layer.setCustomProperty('embeddedWidgets/count', totalEW + 1 )
            layer.setCustomProperty(f"embeddedWidgets/{totalEW}/id", self.widgetProvider.id() )
            project.addMapLayer( layer )
            root = project.layerTreeRoot()
            ltl = root.findLayer( layer )
            ltl.setExpanded(True)

        msg = f"Adding layer collection from {self.data['url']}"
        msg = f"{msg}(version {self.data['version']})..."
        self.msgBar.pushMessage( self.MODULE, msg, Qgis.Info, 0 )
        # Task
        args = {
            'description': self.MODULE,
            'function': createLayer,
            'year': self.data['years']['max'],
            'l_class_id': [1, 10, 14, 22, 26, 27],
            'on_finished': finished
        }
        task = QgsTask.fromFunction( **args )
        self.taskManager.addTask( task )
