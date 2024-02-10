**Note**: This example is only available in German.

## Überblick
In diesem Beispiel wird gezeigt wie man ein kleines Szenario samt Fahrzeugen, Strecken, Fahrten, Depot usw. mit `eflips-model` modellieren kann.

## Dateistruktur
- Das Beispiel ist im Jupyter Notebook `example_scenario.ipynb` enthalten. Dort sind auch nötige Vorbereitungsmaßnahmen beschrieben (zu installierende Packages etc.)
- Die Datei `Netzplan.png` enthält u.a. eine Grafik des modellierten Netzes, die Grafik wird im Jupyter Notebook eingebunden.
- Die Datei `Netzplan.pub` ist die Quelldatei für die Grafik `Netzplan.png`, die mit Microsoft Publisher erstellt wurde.

## Vorbereitung und Ausführung

*Bitte zunächst den gesamten nachfolgenden Text lesen, bevor das Jupyter Notebook ausgeführt bzw. das Virtual Environment erstellt wird.*

Vor Ausführung des Notebooks wird empfohlen, ein eigenes Virtual Environment für dieses Beispiel anzulegen und dort die benötigten Packages zu installieren. Welche Packages benötigt werden, ist im Jupyter Notebook beschrieben.

Da ```eflips-model``` nur über PyPI beziehbar ist, kann es nicht direkt mit Conda usw. benutzt werden.
Daher stattdessen bitte bspw. `pip` verwenden (d.h. `Virtualenv` o.Ä. für das Environment nutzen).

Um das Notebook auszuführen, wird Jupyter Lab benötigt. Dieses kann mit `pip install jupyterlab` im verwendeten Environment installiert werden.

Starten von Jupyter Lab mit
```jupyter lab```
und dort die `example_scenario.ipynb` über den Dateiexplorer rechts öffnen