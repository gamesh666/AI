"""Simulation / development mode for the AI VMS platform.

Everything here replaces real hardware for development and demos:

    aivms_sim.edge   edge-agent plugin: "mock" detector, mock:// and file:// camera sources, simulated GPU metrics
    aivms_sim.seed   creates the demo sites / edge devices / cameras through the public REST API

Production images never install this package; the platform itself does not import it.
"""

__version__ = "0.1.0"
