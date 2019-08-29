# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : MapBiomas Collection
Description          : This plugin lets you get collection of mapping from MapBiomas Project(http://mapbiomas.org/).
Date                 : August, 2019
copyright            : (C) 2019 by Luiz Motta
email                : motta.luiz@gmail.com

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
__author__ = 'Luiz Motta'
__date__ = '2019-08-28'
__copyright__ = '(C) 2019, Luiz Motta'
__revision__ = '$Format:%H$'


import os

from qgis.PyQt.QtCore import Qt, QObject, pyqtSlot, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .mapbiomascollection import DockWidgetMapbiomasCollection

def classFactory(iface):
  return MapbiomasCollectionPlugin( iface )

class MapbiomasCollectionPlugin(QObject):
  def __init__(self, iface):
    super().__init__()
    self.iface = iface
    self.name = u"&MapbiomasCollection"
    self.dock = None

  def initGui(self):
    name = "Mapbiomas Collection"
    about = 'Add a MapBiomas collection'
    icon = QIcon( os.path.join( os.path.dirname(__file__), 'mapbiomas.svg' ) )
    self.action = QAction( icon, name, self.iface.mainWindow() )
    self.action.setObjectName( name.replace(' ', '') )
    self.action.setWhatsThis( about )
    self.action.setStatusTip( about )
    self.action.setCheckable( True )
    self.action.triggered.connect( self.run )

    self.iface.addToolBarIcon( self.action )
    self.iface.addPluginToMenu( self.name, self.action )

    self.dock = DockWidgetMapbiomasCollection( self.iface )
    self.iface.addDockWidget( Qt.LeftDockWidgetArea , self.dock )
    self.dock.visibilityChanged.connect( self.dockVisibilityChanged )

  def unload(self):
    self.iface.removeToolBarIcon( self.action )
    self.iface.removePluginMenu( self.name, self.action )

    self.dock.close()
    del self.dock
    self.dock = None

    del self.action

  @pyqtSlot()
  def run(self):
    if self.dock.isVisible():
      self.dock.hide()
    else:
      self.dock.show()

  @pyqtSlot(bool)
  def dockVisibilityChanged(self, visible):
    self.action.setChecked( visible )
