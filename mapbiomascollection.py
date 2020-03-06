import os, json
import urllib.parse

from osgeo import gdal

from qgis.PyQt.QtCore import Qt, QSettings, QLocale, pyqtSlot
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
    QgsMapSettings,
    QgsTask, QgsMapRendererParallelJob
)
from qgis.gui import QgsGui, QgsMessageBar, QgsLayerTreeEmbeddedWidgetProvider

from qgis import utils as QgsUtils


class MapBiomasCollectionWidget(QWidget):
    nameModulus = 'MapBiomasCollection'
    fileSnapshot = os.path.join( os.path.dirname(__file__), 'snapshot.tif' )
    def __init__(self, layer, data):
        def getYearClasses():
            def getYear():
                values = [ item for item in paramsSource if item.find('year=') > -1 ]
                return self.maxYear if not len( values ) == 1 else int( values[0].split('=')[1] )

            def getClasses():
                values = [ item for item in paramsSource if item.find('classification_ids=') > -1 ]
                return [1,10,14,22,26,27] \
                    if not len( values ) == 1 \
                    else [ int( item ) for item in values[0].split('=')[1].split(',') ]

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
        self.startLayer = True
        self.version = data['version']
        self.url = data['url']
        self.minYear = data['years']['min']
        self.maxYear = data['years']['max']

        self.keyProperty = 'MapBiomasCollectionWidget'
        self.valueProperty = 'layer_before'

        self.mapCanvas = QgsUtils.iface.mapCanvas()
        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()
        self.taskManager = QgsApplication.taskManager()

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
        self.mapCanvas.mapCanvasRefreshed.connect( self.on_mapCanvasRefreshed )
        self.slider.valueChanged.connect( self.on_yearChanged )
        self.slider.sliderReleased.connect( self.on_released )
        self.pbMin.clicked.connect( self.on_limitYear )
        self.pbMax.clicked.connect( self.on_limitYear )
        self.tree.itemChanged.connect( self.on_classChanged )

    def _uploadSource(self):
        """
        Will be create Widget again, finished() -> self.layer.setDataSource
        """
        def finished(exception, result=None):
            def getIndexParentLayer():
                ltl = self.root.findLayer( self.layer )
                parent = ltl.parent()
                index = -1
                for child in parent.children():
                    index += 1
                    if ltl == child:
                        break
                return index, parent

            if not exception is None:
                msg = f"Error: {exception}"
                self.msgBar.pushMessage( msg, Qgis.Critical, 4 )
                return

            layerSnapshot = QgsRasterLayer( self.fileSnapshot, self.layer.name(), 'gdal' )
            self.project.addMapLayer( layerSnapshot, False )
            layerSnapshot.setCustomProperty( self.keyProperty, self.valueProperty )
            index, parent = getIndexParentLayer()
            ltl = parent.insertLayer( index+1, layerSnapshot )
            ltl.setItemVisibilityChecked( True )

            url = self.getUrl( self.url, self.version, self.year, self.l_class_id )
            name = f"Collection {self.version} - {self.year}"
            args = ( url, name, self.layer.providerType(), self.layer.dataProvider().ProviderOptions() )
            self.startLayer = False
            self.layer.setDataSource( *args ) # Will be create Widget again

        def createSnapshot(task):
            def setGeoreference():
                e = self.mapCanvas.extent()
                imgWidth, imgHeight = image.width(), image.height()
                resX, resY = e.width() / imgWidth, e.height() / imgHeight
                gt = ( e.xMinimum(), resX, 0, e.yMaximum(), 0, -1 * resY )

                ds = gdal.Open( self.fileSnapshot, gdal.GA_Update )
                ds.SetGeoTransform( gt )
                crs = self.mapCanvas.mapSettings().destinationCrs()
                ds.SetProjection( crs.toWkt() )
                ds = None

            settings = QgsMapSettings( self.mapCanvas.mapSettings() )
            settings.setBackgroundColor( QColor( Qt.transparent ) )
            settings.setLayers( [ self.layer ] )
            job = QgsMapRendererParallelJob( settings ) 
            job.start()
            job.waitForFinished()
            image = job.renderedImage()
            if bool( self.mapCanvas.property('retro') ):
                image = image.scaled( image.width() / 3, image.height() / 3 )
                image = image.convertToFormat( image.Format_Indexed8, Qt.OrderedDither | Qt.OrderedAlphaDither )
            image.save( self.fileSnapshot, "TIFF", 100 ) # 100: Uncompressed
            setGeoreference()

        self.setEnabled( False )
        self.mapCanvas.mapCanvasRefreshed.disconnect( self.on_mapCanvasRefreshed ) # It will be reconnect when create Widget again
        msg = 'Updating...'
        self.msgBar.pushMessage( msg, Qgis.Info, 4 )
        task = QgsTask.fromFunction( msg, createSnapshot, on_finished=finished )
        task.setDependentLayers( [ self.layer ] )
        self.taskManager.addTask( task )

    @staticmethod
    def getUrl(url, version, year, l_class_id):
        l_strClass = [ str(item) for item in l_class_id ]
        paramsWms = 'IgnoreGetFeatureInfoUrl=1&IgnoreGetMapUrl=1&crs=EPSG:3857&dpiMode=7&format=image/png&layers=coverage&styles='
        paramsQuote = f"map=wms/v/{version}/classification/coverage.map"
        paramsQuote = f"{paramsQuote}&layers=coverage&transparent=true&version=1.1.1&territory_id=10"
        paramsQuote = urllib.parse.quote( f"{paramsQuote}&year={year}&classification_ids=" )
        paramClassification = ','.join( l_strClass )
        return f"{paramsWms}&url={url}?{paramsQuote}{paramClassification}"

    @pyqtSlot()
    def on_mapCanvasRefreshed(self):
        self.slider.setFocus()
        # Remove layerSnapshot if create Widget again
        if not self.startLayer:
            return
        ltl = self.root.findLayer( self.layer )
        parent = ltl.parent()
        hasSnapshot = lambda ltl: not ltl.layer().customProperty( self.keyProperty, None) is None
        l_ltl = [ ltl for ltl in parent.findLayers() if hasSnapshot( ltl ) ]
        for ltl in l_ltl:
            parent.removeChildNode( ltl )

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
        status = item.checkState( column ) == Qt.Checked
        f = self.l_class_id.append if status else self.l_class_id.remove
        f( value )
        self._uploadSource() # Will be create Widget again


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
        host = f"url={self.data['url']}?map=wms/v/{self.data['version']}/classification/coverage.map"
        l_url = [ item for item in source if item.find( host ) > -1 ]
        return len( l_url ) > 0


class MapBiomasCollection():
    def __init__(self):
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

            with open(fileConfig) as json_file:
                data = json.load(json_file)    
            return data

        self.data = getConfig()
        self.widgetProvider = None

    def __del__(self):
        if os.path.exists( MapBiomasCollectionWidget.fileSnapshot ):
            os.remove( MapBiomasCollectionWidget.fileSnapshot )

    def register(self):
        self.widgetProvider = LayerMapBiomasCollectionWidgetProvider( self.data )
        registry = QgsGui.layerTreeEmbeddedWidgetRegistry()
        if not registry.provider( self.widgetProvider.id() ) is None:
            registry.removeProvider( self.widgetProvider.id() )
        registry.addProvider( self.widgetProvider )

    def run(self):
        def createLayer(year, l_class_id):
            args = ( self.data['url'], self.data['version'], year, l_class_id )
            url = MapBiomasCollectionWidget.getUrl( *args )
            return QgsRasterLayer( url, f"Collection {self.data['version']} - {year}", 'wms' )

        def addLayer(layer):
            project = QgsProject.instance()
            totalEW = int( layer.customProperty('embeddedWidgets/count', 0) )
            layer.setCustomProperty('embeddedWidgets/count', totalEW + 1 )
            layer.setCustomProperty(f"embeddedWidgets/{totalEW}/id", self.widgetProvider.id() )
            project.addMapLayer( layer )
            root = project.layerTreeRoot()
            ltl = root.findLayer( layer )
            ltl.setExpanded(True)

        layer = createLayer(2018, [1, 10, 14, 22, 26, 27])
        addLayer( layer )
