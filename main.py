"""
TO DO:

Aircraft advanced pathfinding (ILS, navaids, etc)
Airspace boundaries - Func needs fixing
If x,y in area function - See above
Controls for aircraft from cmd
Link cmd to voice
Automatic callups
Scenario loading and setup (incl new aircraft, disappear on boundary exit)
Controller coordination
Weather environment link i.e. aircraft respond to weather
"""

# IMPORTS
import tkinter as tk
from tkinter import font
from math import radians, sin, cos
import random
import json
import threading
import time

# GLOBALS
IMPORTED = "EGDM.json"  # input req
try:
    with open(IMPORTED) as f:
        EXERCISE = json.load(f)
except Exception as err:
    raise err
TITLE = "Radar Controller Simulation"
SCREEN_BG = "#c3c3c3"
BLIP_FADE = "#00f"
SCREEN_FG = "#000"
IDENT_COLOUR = "#0f0"  # Change to pink? green atm (red conflict, blue controlled...)
IDENT_COUNT_MAX = 5
SCALE_FACTOR = 12  # SFpx = 1nm (higher SF = more zoom)
TICK_DURATION = 4000  # ms
PAUSED = True
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DISPLAY = {"TICKED": False,  # Print when sim ticks in terminal
           "C/S_SSR": "SSR",  # Callsign or squawk on label (C/S, SSR)
           "RINGS": False,  # Toggles range rings on master airport
           "RINGS_N": 3,  # Number of rings (>=1)
           "RINGS_D": 10,  # nm between each ring (>=1)
           "LINES": False,  # Toggles lines in front of aircraft
           "LINES_M": "Time",  # Mode switch time (2min) and distance (2mi) (unless changed increase/decrease)
           "LINES_N": 2,  # Default integer for lines mode (x min/mi)
           "CRUMBS": False,  # Toggles breadcrumbs for location history on blips
           "CONTROLLED": False,  # Toggles colour for uncontrolled aircraft,
           "EST_ALT_REACH": False,  # Toggles line on blip heading for estimated altitude reach point (climb/descent)
           "AIRSPACE": False,  # Toggles CTA boundary visual
           "CTA_WIDTH": 1,  # Width of boundary line (>=1)
           "EXTRA_LABEL": False,  # Toggles extra label details (i.e. airspeed, etc (otherwise just CS/SSR and alt))
           "VISUAL_LABEL": "VISUAL CONTROLS",  # Label text for visual controls on left side
           "SIM_LABEL": "SIM CONTROLS",  # Label text for sim controls on left side,
           "SIM_SPEED": 1,  # Multiplier for TICK_DURATION
           "WEATHER": "OFF",  # Toggles OFF RANDOM LIVE
           "LIVE_WEATHER": {},  # Live weather for aircraft to be affected by
           }
if "display_override" in EXERCISE.keys():
    for k in EXERCISE["display_override"]:
        DISPLAY[k] = EXERCISE["display_override"][k]
DISPLAY_OLD = DISPLAY.copy()  # For reset display option

# GLOBAL FUNCTIONS
def px2nm(px):
    """Converts pixels into nautical miles based on scale factor."""
    return px / SCALE_FACTOR
    

def nm2px(nm):
    """Converts nautical miles into pixels based on scale factor."""
    return nm * SCALE_FACTOR


def dist2m(speed_kts, dist, unit):
    """Calculates the distance (nm) travelled by an object in d units, based on its speed in knots."""
    if unit == "Time":
        t = dist / 60
        return speed_kts * t
    elif unit == "Dist":
        return dist


def randomRegistration(origin="G"):
    """Generates a random aircraft registration. Takes a country origin (default 'G')."""
    reg = list(f"{origin}----")
    for i in range(len(reg)):
        if reg[i] == "-":
            reg[i] = random.choice(LETTERS)
    return "".join(reg)


def randomWeather(icao_code):
    """Generates random weather into a weather package."""
    from datetime import datetime as dt
    categories = {"cavok": {"hpa": (1010, 1020),
                            "clouds": None,
                            "temperature": (13, 25),
                            "visibility": (9999, 9999),
                            "wind_kts": (0, 10)},
                  "vfr": {"hpa": (1000, 1018),
                          "clouds": (3000, 5000),
                          "temperature": (5, 25),
                          "visibility": (8000, 9800),
                          "wind_kts": (1, 15)},
                  "mvfr": {"hpa": (1000, 1018),
                           "clouds": (1000, 3000),
                           "temperature": (-1, 20),
                           "visibility": (4800, 8000),
                           "wind_kts": (2, 15)},
                  "ifr": {"hpa": (995, 1014),
                          "clouds": (500, 1500),
                          "temperature": (-5, 15),
                          "visibility": (1600, 4800),
                          "wind_kts": (3, 20)},
                  "lifr": {"hpa": (985, 1005),
                           "clouds": (100, 800),
                           "temperature": (-7, 12),
                           "visibility": (100, 1500),
                           "wind_kts": (4, 25)}}
    category = random.choice(list(categories.keys()))
    cat = categories[category]
    temp = random.randint(*cat["temperature"])
    weather_package = {"icao": icao_code.upper(),
                       "barometer": random.randint(*cat["hpa"]),
                       "temperature": temp,
                       "dewpoint": int(temp - random.randint(0, 7)),
                       "visibility": round(random.randint(*cat["visibility"]), -2) if cat["visibility"][0] != cat["visibility"][1] else cat["visibility"][0],
                       "wind": {"degrees": round(random.randint(1, 360), -1), "speed": random.randint(*cat["wind_kts"])}}  # random clouds req
    t = dt.now()
    raw_text = f"{icao_code.upper()} {'0' if t.day < 10 else ''}{t.day}{'0' if t.hour < 10 else ''}{t.hour}{'0' if t.minute < 10 else ''}{t.minute}Z "
    raw_text += f"AUTO {'0'*(3-len(str(weather_package['wind']['degrees'])))}{weather_package['wind']['degrees']}"
    raw_text += f"{'0' if weather_package['wind']['speed'] < 10 else ''}{weather_package['wind']['speed']}KT {weather_package['visibility']} "
    order = ("FEW", "SCT", "BKN", "OVC")
    if cat["clouds"] is None:
        raw_text += "NCD "
    else:
        cs = ""
        used = []
        alts = []
        lower, upper = cat["clouds"]
        num = random.randint(0, 2)
        if num == 0:
            raw_text += "NCD "
            cs = "NCD "
        else:
            for i in range(num):
                if i == 0:
                    fs = random.choice((order[0], order[1]))
                    while fs in used:
                        fs = random.choice((order[0], order[1]))
                else:
                    latest = order.index(used[-1]) if used != [] else -1
                    ind = latest + 1
                    try:
                        fs = random.choice((order[i], order[i+1]))
                        if fs in used:
                            raise IndexError
                    except IndexError:
                        try:
                            fs = order[i]
                            if fs in used:
                                raise IndexError
                        except IndexError:
                            continue
                        except Exception as err:
                            raise err
                    except Exception as err:
                        raise err
                alt = random.randint(lower if alts == [] else alts[-1], upper)
                alt = round(alt, -2)
                alts.append(alt)
                alt = str(alt)[:-2]
                while len(alt) < 3:
                    alt = "0" + alt
                c = fs + alt
                used.append(fs)
                raw_text += c + " "
                cs += c + " "
        weather_package["clouds"] = cs
    
    # DEW POINT LEADING ZERO
    if weather_package["temperature"] in range(1, 11):
        weather_package["temperature"] = "0" + str(weather_package["temperature"])
    elif weather_package["temperature"] <= 0:
        weather_package["temperature"] = "M" + ("0" if weather_package["temperature"] > -10 else "") + str(weather_package["temperature"]).replace("-", "")
    if weather_package["dewpoint"] in range(1, 11):
        weather_package["dewpoint"] = "0" + str(weather_package["dewpoint"])
    elif weather_package["dewpoint"] <= 0:
        weather_package["dewpoint"] = "M" + ("0" if weather_package["dewpoint"] > -10 else "") + str(weather_package["dewpoint"]).replace("-", "")
    raw_text += f"{weather_package['temperature']}/{weather_package['dewpoint']} Q{'0' if weather_package['barometer'] < 1000 else ''}{weather_package['barometer']}"
    weather_package["raw_text"] = raw_text
    return weather_package


def liveWeather(icao_code, api_key="a4be9e1dd79d4e75a55102a941"):
    """Pulls live weather for the airport and converts it into a weather package."""
    from requests import get, exceptions
    url = "https://api.checkwx.com/metar/" + icao_code.upper() + "/decoded?key=" + api_key
    try:
        r = get(url)
    except exceptions.ConnectionError as err:
        return {"raw_text": "INTERNET FAILED"}
    except Exception as err:
        raise err
    else:
        try:
            metar = r.json()["data"][0]
        except Exception as err:
            raise err
        else:
            return metar


def plotCTA(x, y, points):
    """Uses the coordinate points from the defined CTA (list[tuple]) to draw lines between for plotting later."""
    points = points.copy()  # Otherwise, overwrites existing cta boundary
    if points[-1] != points[0]:
        points.append(points[0])
    for i, point in enumerate(points):
        p1, p2 = point
        points[i] = (nm2px(p1), nm2px(p2))
    lines = []
    for p in range(len(points)):
        try:
            p1, p2 = points[p], points[p+1]
            z = [*p1, *p2]
            for zz in range(len(z)):  # Clunky variable names, yes, I know...
                if zz % 2 == 0:
                    z[zz] = z[zz]+y
                else:
                    z[zz] = z[zz]+x
            lines.append(z)
        except IndexError:
            break
        except Exception as err:
            raise err
    return lines


def pointInCircle(x, y, center_x, center_y, radius, on=True):
    """Returns True/False if coordinate within circle. 'on' = inclusive."""
    if on:
        return ((x-center_x) ** 2) + ((y-center_y) ** 2) <= (radius ** 2)
    else:
        return ((x-center_x) ** 2) + ((y-center_y) ** 2) < (radius ** 2)


def doLinesCross(line1a, line1b, line2a, line2b):
    """Checks if two lines meet at any point within their domain."""
    x1, y1 = line1a
    x2, y2 = line1b
    x3, y3 = line2a
    x4, y4 = line2b
    
    # Handle vertical lines explicitly (infinite slope)
    if x1 == x2:  # Line 1 is vertical
        x = x1
        if x3 != x4:  # Line 2 is not vertical
            line2m = (y4 - y3) / (x4 - x3)
            line2c = y3 - line2m * x3
            y = line2m * x + line2c
        else:  # Both lines are vertical and parallel
            return False
    elif x3 == x4:  # Line 2 is vertical
        x = x3
        line1m = (y2 - y1) / (x2 - x1)
        line1c = y1 - line1m * x1
        y = line1m * x + line1c
    else:
        # Calculate slopes and intercepts
        line1m = (y2 - y1) / (x2 - x1)
        line2m = (y4 - y3) / (x4 - x3)
        
        # Parallel lines have no intersection
        if line1m == line2m:
            return False
        
        # Calculate intersection point
        line1c = y1 - line1m * x1
        line2c = y3 - line2m * x3
        
        x = (line2c - line1c) / (line1m - line2m)
        y = line1m * x + line1c
    
    # Check if the intersection point is within the segment bounds
    if min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2) and \
       min(x3, x4) <= x <= max(x3, x4) and min(y3, y4) <= y <= max(y3, y4):
        return x, y  # Return the intersection point
    
    return False  # No intersection

    
def pointInPoly(x, y, corners):
    """Checks if a coordinate point is within a polygon defined with points. Currently broken as returns False for all cases, even if meant to be True..."""
    raise Exception("!!!BROKEN FUNCTION CALLED!!!")
    point_line = ((x, y), (999, y))
    poly_lines = []
    for i in range(len(corners)):
        try:
            p1, p2 = corners[i], corners[i+1]
        except IndexError:
            p1, p2 = corners[i], corners[0]
        except Exception as err:
            raise err
        else:
            poly_lines.append((p1, p2))
    intersections = 0
    for line in poly_lines:
        line2 = list(line)
        for i in range(len(line2)):
            line2[i] = [nm2px(line2[i][0]), nm2px(line2[i][1])]
        intersect = doLinesCross(*point_line, *line2)
        print(intersect)
        print(point_line)
        print(line2)
        if intersect:
            intersections += 1
    print(intersections)
    return intersections % 2 == 1


# CLASSES
class Airport:
    def __init__(self, x, y, rwy_hdg, icao_code, name, auto_draw_canvas=None, auto_draw=True,
                 cta_boundary=None, atc_stations=[], ils="3500@10", ils_end_nm=15, master=False):
        self.x = x
        self.y = y
        self.rwy_hdg = rwy_hdg
        self.icao = icao_code
        self.name = name
        self.master = master
        self.icon_radius = nm2px(1)  # 1nm radius
        self.centerline_length = 10  # nm
        self.half_minor_centerlines = False
        self.cta_boundary = cta_boundary
        self.marker_length = 7  # Trial and error for aesthetics (arbitrary)
        self.all_drawn = []
        self.stations = [Station(s["name"], s["vhf_frequency"], s["type"],
                                 atz_radius=s["atz_radius_nm"] if "atz_radius_nm" in s.keys() else None,
                                 boundary=s["boundary_plot"] if "boundary_plot" in s.keys() else None,
                                 isuser=s["is_user"]) for s in atc_stations]
        self.atz_radius = None
        self.ils_alt_10nm = self.calc_ils_alt(ils)
        self.ils_end_nm = ils_end_nm
        self.ils_waypoints = self.generateILSWaypoints()
        for station in self.stations:
            if station.type == "tower" and type(station.cta) in (int, float):
                self.atz_radius = station.cta
        if auto_draw:
            self.draw(auto_draw_canvas)

    def generateILSWaypoints(self):
        alts = {str(i): None for i in range(1, self.ils_end_nm + 1)}
        xy = {str(self.rwy_hdg): {str(i): None for i in range(1, self.ils_end_nm + 1)},
              str(self.rwy_hdg + 180): {str(i): None for i in range(1, self.ils_end_nm + 1)}}
        alts["10"] = self.ils_alt_10nm
        rate_of_descent = self.ils_alt_10nm / 10
        distance = 1
        for k in alts:
            alts[k] = distance * rate_of_descent
            distance += 1
        for k in xy:
            rwy_angle = float(k)
            rwy_angle = radians(rwy_angle)
            for j in xy[k]:
                distance = int(j)
                y = -cos(rwy_angle) * nm2px(distance)
                x = sin(rwy_angle) * nm2px(distance)
                y += self.y
                x += self.x
                xy[k][j] = [x, y]
        self.ilsAlts = alts
        self.ilsXY = xy

    def generateILSRoute(self, rwy_hdg):
        route = []
        for nm in self.ilsXY[str(rwy_hdg)]:
            alt = self.ilsAlts[nm]
            x, y = self.ilsXY[str(rwy_hdg)][nm]
            nm = float(nm)
            if nm <= 4:
                speed = 120
            elif nm <= 6:
                speed = 160
            elif nm <= 10:
                speed = 180
            else:
                speed = 190
            route.append({"x": x, "y": y, "alt": alt, "hdg": None, "kts": speed})
        return route

    def calc_ils_alt(self, ils):
        alt, dist = ils.split("@")
        alt = float(alt)
        dist = float(dist)
        scale = alt / dist
        alt_10 = scale * 10
        return alt_10

    def draw(self, canvas):
        for k in self.ilsXY:
            for i, j in enumerate(self.ilsXY[k]):
                x, y = self.ilsXY[k][j]
                # self.all_drawn.append(canvas.create_oval(x-1, y-1, x+1, y+1)) DRAW ILS WAYPOINTS
                # self.all_drawn.append(tk.Label(canvas, text=str(self.ilsAlts[str(i+1)])).place(x=x, y=y))


        centerline_package = self.rwy_centerlines()
        for x, y in centerline_package:
            self.all_drawn.append(canvas.create_line(self.x, self.y, x, y, fill=SCREEN_FG))
        label = tk.Label(canvas, text=self.icao, bg=SCREEN_BG, fg=SCREEN_FG)
        label.place(x=self.x+5, y=self.y+5)
        self.all_drawn.append(label)
        # Square for middle icon
        self.all_drawn.append(canvas.create_oval(self.x-self.icon_radius,
                                                 self.y-self.icon_radius,
                                                 self.x+self.icon_radius,
                                                 self.y+self.icon_radius,
                                                 fill=SCREEN_BG,
                                                 outline=SCREEN_BG))  # Oval to stop centerlines overlapping w/ square
        self.all_drawn.append(canvas.create_rectangle(self.x-self.icon_radius/4,
                                                      self.y-self.icon_radius/4,
                                                      self.x+self.icon_radius/4,
                                                      self.y+self.icon_radius/4,
                                                      fill=SCREEN_BG,
                                                      outline=SCREEN_FG))
        # Range rings (10, 20, 30, 40 nm)
        if self.master:
            if DISPLAY["RINGS"]:
                for i in range(1, DISPLAY["RINGS_N"] + 1):
                    radius = nm2px(i * DISPLAY["RINGS_D"])
                    self.all_drawn.append(canvas.create_oval(self.x-radius,
                                                             self.y-radius,
                                                             self.x+radius,
                                                             self.y+radius,
                                                             outline=SCREEN_FG))
            self.range_markers((self.x, self.y), self.rwy_hdg, canvas)
            if DISPLAY["AIRSPACE"]:
                for i, line in enumerate(self.cta_boundary):
                    try:
                        x2, y2 = self.cta_boundary[i+1]
                    except IndexError:
                        x2, y2 = self.cta_boundary[0]
                    finally:
                        x1, y1 = line
                    x1 = nm2px(x1)
                    y1 = nm2px(y1)
                    x2 = nm2px(x2)
                    y2 = nm2px(y2)
                    x1 += self.x
                    x2 += self.x
                    y1 += self.y
                    y2 += self.y
                    self.all_drawn.append(canvas.create_line(x1, y1, x2, y2, fill=SCREEN_FG, dash=".", width=DISPLAY["CTA_WIDTH"]))
            if self.atz_radius is not None:
                radius = nm2px(self.atz_radius)
                self.all_drawn.append(canvas.create_oval(self.x-radius, self.y-radius,
                                                            self.x+radius, self.y+radius,
                                                            outline=SCREEN_FG, dash="-", width=1))
                    
    def rwy_centerlines(self):
        length = self.centerline_length
        if self.half_minor_centerlines and not self.master:
            length /= 2
        package = []
        length = nm2px(length)
        rads = radians(self.rwy_hdg)
        width = sin(rads) * length
        height = -cos(rads) * length
        package.append((self.x + width, self.y + height))
        rads = radians(self.rwy_hdg + 180)
        width = sin(rads) * length
        height = -cos(rads) * length
        package.append((self.x + width, self.y + height))
        return package
    
    def range_markers(self, origin, heading, canvas):
        d = nm2px(1)
        for _ in range(2):
            hdg = radians(heading - 10)  # needs fixing
            angle = hdg+radians(90)
            dy = -sin(hdg) * d
            dx = cos(hdg) * d
            coords = []
            x, y = origin
            for i in range(self.centerline_length):
                x += dx
                y += dy
                coords.append((x, y))
            i = 0
            for x, y in coords:
                i += 1
                length = self.marker_length
                if i % 5 == 0:
                    length *= 2
                dy = -sin(angle) * length
                dx = cos(angle) * length
                coord1 = (x + dx, y + dy)
                dy = -cos(angle) * length
                dx = sin(angle) * length
                coord2 = (x + dx, y + dy)
                self.all_drawn.append(canvas.create_line(*coord1, *coord2))
            heading += 180

    def clear(self, canvas):
        for item in self.all_drawn:
            try:
                canvas.delete(item)
            except Exception as err:
                try:
                    item.destroy()
                except Exception as err:
                    raise err
        self.all_drawn = []


class Blip:
    def __init__(self, x, y, hdg, kts, callsign, altitude, squawk, route,
                 active_station=None, auto_draw_canvas=None, auto_draw=True):
        self.x = x
        self.y = y
        self.hdg = hdg
        self.kts = kts
        self.callsign = callsign
        self.squawk = squawk
        self.route = route
        self.location_history = []
        self.altitude = altitude
        self.altitude_history = []
        self.selected_ils = None
        self.conflicting = False  # Needs testing
        self.blip_radius = 5
        self.atc_package = {"controlled": False,
                            "phase": None,
                            "ident": False,
                            "ident_count": 0}
        self.conflict_count = 0
        self.all_drawn = []
        self.active_station = active_station
        if auto_draw: self.draw(auto_draw_canvas)

    def loadILS(self, icao, rwy, replace=False, routeThere=None):
        ILSroute = sim.airports[icao].generateILSRoute(rwy)
        ILSroute = ILSroute[::-1]  # ILSroute[-1] is first point on localiser
        if routeThere:
            ILSroute.insert(0, routeThere)
        if replace:
            self.route = ILSroute
        else:
            for point in ILSroute:
                self.route.append(point)
        self.selected_ils = "/".join((icao, str(rwy)))
        print("Loaded ILS", self.route)

    def altitude_direction(self):
        char = "-"
        if self.altitude_history != []:
            latest = self.altitude_history[-1]
            if latest > self.altitude:
                char = "v"
            elif latest < self.altitude:
                char = "^"
        return char

    def alt_to_lbl(self):
        alt = round(self.altitude, -2) // 100
        alt = str(int(alt))
        while len(alt) < 3:
            alt = "0" + alt
        return alt

    def addWaypointToRoute(self, navaid, alt=None, kts=None, append_=True):
        if navaid in EXERCISE["scenery"]["navaids"]:
            x, y = EXERCISE["scenery"]["navaids"][navaid]["xy_nm"]
            x = EXERCISE["middle"] + nm2px(x)
            y = EXERCISE["middle"] + nm2px(y)
            r = {"x": x, "y": y, "hdg": None, "alt": alt, "kts": kts}
            if append_:
                self.route.append(r)
            else:
                return r

    def hdg_to_coord(self, dist, unit):
        length = nm2px(dist2m(self.kts, dist, unit))
        rads = radians(self.hdg)
        width = sin(rads) * length
        height = -cos(rads) * length
        return self.x + width, self.y + height

    def coord_to_hdg(self, x, y):
        from math import atan2, degrees
        dx = x - self.x
        dy = y - self.y
        rads = atan2(dx, -dy)
        degs = degrees(rads)
        return (degs + 360) % 360

    def move(self, canvas):
        def convertFirstRoutePoint():
            if self.route != []:
                if "navaid" in self.route[0]:
                    self.selected_ils = None
                    self.route[0] = self.addWaypointToRoute(self.route[0]["navaid"], alt=self.route[0]["alt"], kts=self.route[0]["kts"], append_=False)
                elif "code" in self.route[0]:  # load for specific rwy required
                    self.loadILS(self.route[0]["code"], rwy=self.route[0]["rwy"], replace=self.route[0]["replace"], routeThere=self.route[0]["routeThere"])
                else:
                    raise Exception("to do")
                x, y = self.route[0]["x"], self.route[0]["y"]
                if pointInCircle(self.x, self.y, x, y, nm2px(1)):  # Success if within 1nm radius of waypoint
                    self.route.pop(0)  # next iter req (no alt in raw ils point)
                    convertFirstRoutePoint()
                else:
                    hdg = self.coord_to_hdg(x, y)
                    self.route[0]["hdg"] = hdg
            
        print(self.selected_ils)
        if self.selected_ils is not None:
            print("pic", pointInCircle(self.x, self.y, sim.airports[self.selected_ils.split("/")[0]].x, sim.airports[self.selected_ils.split("/")[0]].y, radius=nm2px(2)))
            # BROKEN
            raise
            if pointInCircle(self.x, self.y, sim.airports[self.selected_ils.split("/")[0]].x, sim.airports[self.selected_ils.split("/")[0]].y, radius=nm2px(2)):
                print(self.route)
                if len(self.route) <= 1:
                    del sim.blips[self.callsign]  # Delete this blip
                else:
                    convertFirstRoutePoint()  # More routing after ILS touchdown e.g., go around
            else:
                convertFirstRoutePoint()
        else:
            convertFirstRoutePoint()

        # ALTITUDE
        if self.selected_ils is None:
            vertical_speed = 200  # random?
            t = (TICK_DURATION * DISPLAY["SIM_SPEED"]) / 1000
            t /= 60
            vertical_speed *= t
        else:
            vertical_speed = None
        if self.route != [] and self.route[0]["alt"] is not None:
            if vertical_speed is not None:
                if self.route[0]["alt"] < self.altitude:
                    vertical_speed *= -1
                next_altitude = self.altitude + vertical_speed
            else:  # vs is None => ILS enabled
                next_altitude = self.route[0]["alt"]
                alt_diff = self.altitude - next_altitude
                dx = self.x - self.route[0]["x"]
                dy = self.y - self.route[0]["y"]
                dist = (dx ** 2) + (dy ** 2)
                dist = dist ** 0.5
                vertical_speed = alt_diff / (dist * self.kts / 60)
                print("VS", vertical_speed)
            self.altitude_history.append(self.altitude)
            if vertical_speed < 0 and next_altitude < self.route[0]["alt"]:
                self.altitude = self.route[0]["alt"]
                self.route[0]["alt"] = None
            elif vertical_speed > 0 and next_altitude > self.route[0]["alt"]:
                self.altitude = self.route[0]["alt"]
                self.route[0]["alt"] = None
            else:
                self.altitude = next_altitude
        else:
            self.altitude_history.append(self.altitude)

        # Need to implement wind drift
        if DISPLAY["LIVE_WEATHER"] != {}:
            wind_deg = DISPLAY["LIVE_WEATHER"]["wind"]["degrees"]
            wind_kts = DISPLAY["LIVE_WEATHER"]["wind"]["speed"]
        else:
            wind_deg = None
            wind_kts = None # CONTINUE

        # HEADING
        """
        degrees_of_bank = 30  # shouldn't need to change
        from math import tan, pi
        radius_of_turn = (self.kts ** 2) / (9.81 * tan(radians(degrees_of_bank)))
        rate_of_turn = radius_of_turn ** -1
        degrees_per_sec = rate_of_turn * (180 / pi)
        time_in_tick = (TICK_DURATION * DISPLAY["SIM_SPEED"])/1000
        degrees = degrees_per_sec * time_in_tick
        """
        degrees_per_sec = 2
        degrees = degrees_per_sec * (TICK_DURATION * DISPLAY["SIM_SPEED"]) / 1000
        if self.route != [] and self.route[0]["hdg"] is not None:
            if self.route[0]["hdg"] > self.hdg:
                next_hdg = self.hdg + degrees
            elif self.route[0]["hdg"] < self.hdg:
                next_hdg = self.hdg - degrees
            else:
                next_hdg = self.hdg
            if next_hdg < self.hdg and next_hdg < self.route[0]["hdg"]:
                self.hdg = self.route[0]["hdg"]
                self.route[0]["hdg"] = None
            elif next_hdg > self.hdg and next_hdg > self.route[0]["hdg"]:
                self.hdg = self.route[0]["hdg"]
                self.route[0]["hdg"] = None
            else:
                self.hdg = next_hdg

        # SPEED
        rate_kts_sec = 2
        rate = rate_kts_sec * (TICK_DURATION * DISPLAY["SIM_SPEED"]) / 1000
        if self.route != [] and self.route[0]["kts"] is not None:
            if self.route[0]["kts"] < self.kts:
                rate *= -1
            next_speed = self.kts + rate
            if next_speed < self.kts and next_speed < self.route[0]["kts"]:
                self.kts = self.route[0]["kts"]
                self.route[0]["kts"] = None
            elif next_speed > self.kts and next_speed > self.route[0]["kts"]:
                self.kts = self.route[0]["kts"]
                self.route[0]["kts"] = None
            else:
                self.kts = next_speed

        unit_time = TICK_DURATION / 1000  # ms -> s
        unit_time /= (60 * 60)  # s -> m -> h
        distance_travelled = nm2px(self.kts * unit_time)  # px
        rads = radians(self.hdg)
        dx = sin(rads) * distance_travelled
        dy = -cos(rads) * distance_travelled
        if DISPLAY["CRUMBS"]:
            other = True
            for x, y in self.location_history:
                if other: self.all_drawn.append(canvas.create_oval(x-1, y-1, x+1, y+1, outline=SCREEN_FG, fill=SCREEN_BG))
                other = not other
        else:
            self.location_history = []
        self.x += dx
        self.y += dy
        self.location_history.append((self.x, self.y))
        while len(self.location_history) > 10:
            self.location_history.pop(0)

        """
        if pointInPoly(self.x, self.y, EXERCISE["scenery"]["airports"][EXERCISE["exercise_info"]["master_airport"]]["cta_boundary_plot_nm"]):  # Used for if blip in cta for contact later
            print(self.callsign+" inside CTA")
        """

    def draw(self, canvas, move=True):
        # Move aircraft due to tick
        if move:
            self.move(canvas)

        if self.atc_package["ident"] and self.atc_package["ident_count"] < IDENT_COUNT_MAX:
            if self.atc_package["ident_count"] % 2 == 0:
                colour = IDENT_COLOUR
            else:
                colour = SCREEN_FG
            self.atc_package["ident_count"] += 1
        elif self.atc_package["controlled"]:
            colour = SCREEN_FG
        elif DISPLAY["CONTROLLED"]:
            colour = BLIP_FADE
        else:
            colour = SCREEN_FG

        if self.atc_package["ident_count"] >= IDENT_COUNT_MAX:
            self.atc_package["ident"] = False
            self.atc_package["ident_count"] = 0

        if self.conflicting:
            self.conflict_count = 1 - self.conflict_count
            if self.conflict_count == 1:
                colour = "#f00"

        blip = canvas.create_oval(self.x-self.blip_radius,
                                  self.y-self.blip_radius,
                                  self.x+self.blip_radius,
                                  self.y+self.blip_radius,
                                  fill=SCREEN_BG,
                                  outline=colour)
        # Primary radar sim (/1.2 is visual estimate)
        cross_y = canvas.create_line(self.x, self.y-self.blip_radius/1.2,
                                     self.x, self.y+self.blip_radius/1.2,
                                     fill=colour)
        cross_x = canvas.create_line(self.x-self.blip_radius/1.2, self.y,
                                     self.x+self.blip_radius/1.2, self.y,
                                     fill=colour)
        if DISPLAY["LINES"]:
            x1, y1 = self.hdg_to_coord(DISPLAY["LINES_N"], DISPLAY["LINES_M"])
            line = canvas.create_line(self.x, self.y, x1, y1, fill=colour)
            self.hdg_line = line
        else:
            self.hdg_line = None
        self.blip = blip
        self.draw_label(canvas, colour="#f00" if colour == "#f00" else None)
        """
        if DISPLAY["CRUMBS"]:
            other = True
            for x, y in self.location_history:
                if other: self.all_drawn.append(canvas.create_oval(x-1, y-1, x+1, y+1, outline=colour, fill=SCREEN_BG))
                other = not other
        """
        if DISPLAY["EST_ALT_REACH"]:
            alt_remaining = abs(self.altitude-self.set_altitude)
            miles_per_min = self.kts / 60
            if self.vertical_speed != 0:
                time_to_alt = alt_remaining / self.vertical_speed
            else:
                time_to_alt = float("inf")  # VS is 0, no change in alt so no point on screen
            if time_to_alt <= 2:
                miles_travelled = miles_per_min*time_to_alt
                distance = nm2px(miles_travelled)
                rads = radians(self.hdg)
                width = sin(rads) * distance
                height = -cos(rads) * distance
                if self.altitude > self.set_altitude:
                    width, height = -width, -height
                point = self.x + width, self.y + height
                radius = 2
                self.all_drawn.append(canvas.create_oval(point[0]-radius, point[1]-radius,
                                                         point[0]+radius, point[1]+radius,
                                                         fill=colour))
        for item in [blip, cross_y, cross_x, self.hdg_line, self.label]:
            self.all_drawn.append(item)
        return canvas

    def draw_label(self, canvas, colour):
        if not pointInCircle(self.x, self.y, 400, 400, nm2px(2)):  # Aircraft inside 2nm radius, too close for radar label
            starter = self.callsign if DISPLAY["C/S_SSR"] == "C/S" else self.squawk
            if DISPLAY["EXTRA_LABEL"]:
                text = f"{starter}\n{self.alt_to_lbl()}{self.altitude_direction()}\n{round(self.kts)}"  # DIRECTION STATIC ATM
            else:
                text = f"{starter}\n{self.alt_to_lbl()}"
            self.label = tk.Label(canvas, text=text, bg=SCREEN_BG, fg=SCREEN_FG if not colour else colour, justify="left")
            self.label.place(x=self.x+5, y=self.y+5)
        else:
            self.label = None

    def clear(self, canvas):
        for item in self.all_drawn:
            try:
                canvas.delete(item)
            except Exception as err:
                try:
                    item.destroy()
                except Exception as err:
                    raise err
        self.all_drawn = []


class Station:
    def __init__(self, name, vhf, type_, atz_radius=None, boundary=None, isuser=False):
        self.name = name
        self.freq = vhf
        self.type = type_
        if atz_radius is not None:
            self.cta = atz_radius
        else:
            self.cta = boundary
        self.user = isuser

    def handover(self, callsign, controller):
        ...


class Sim:
    def __init__(self, root, title):
        # Setup variables
        self.root = root
        self.root.resizable(False, False)
        self.root.title(title)
        self.master_width = 1200
        self.master_height = 800
        self.screen_lengths = self.master_height
        EXERCISE["middle"] = self.screen_lengths / 2
        global SCREEN
        SCREEN = [self.master_width, self.screen_lengths]
        self.screen_lengths_nm = self.screen_lengths//SCALE_FACTOR

        self.blips = {}
        self.airports = {}

        # Configure self.root
        self.root.geometry(f"{self.master_width}x{self.master_height}")

        # Init self.canvas
        self.canvas = tk.Canvas(self.root, height=self.screen_lengths, width=self.screen_lengths, bg=SCREEN_BG)
        self.canvas.pack()

        # Scenery & test blips
        self.draw()

        self.draw_controls()

    def draw(self):
        self.create_scenery()
        self.create_starter_aircraft()

    def clear(self):
        for airport_id in self.airports:
            self.airports[airport_id].clear(self.canvas)
        for blip_id in self.blips:
            self.blips[blip_id].clear(self.canvas)

    def create_scenery(self):
        scenery = EXERCISE["scenery"]
        for airport_code in scenery["airports"]:
            a = scenery["airports"][airport_code]
            self.airports[airport_code] = Airport(x=(self.screen_lengths / 2)+nm2px(a["xy"][0]), y=(self.screen_lengths / 2)+nm2px(a["xy"][1]),
                                                  rwy_hdg=a["runway_heading"], icao_code=airport_code, name=a["name"], auto_draw_canvas=self.canvas,
                                                  cta_boundary=a["cta_boundary_plot_nm"] if "cta_boundary_plot_nm" in a.keys() else None,
                                                  atc_stations=a["atc_stations"] if "atc_stations" in a.keys() else [],
                                                  ils=a["ils_alt@nm"] if "ils_alt@nm" in a.keys() else "3500@10",
                                                  ils_end_nm=a["ils_end_nm"] if "ils_end_nm" in a.keys() else 15,
                                                  master=a["master_airport"] if "master_airport" in a.keys() else False)
            if "master_airport" in a.keys() and a["master_airport"] == True:
                self.master_airport = airport_code
        for navaid in scenery["navaids"]:
            x, y = scenery["navaids"][navaid]["xy_nm"]
            name = scenery["navaids"][navaid]["name"]
            x = (self.screen_lengths / 2) + nm2px(x)
            y = (self.screen_lengths / 2) + nm2px(y)
            self.canvas.create_rectangle(x-1, y-1, x+1, y+1, fill=SCREEN_BG, outline=SCREEN_FG)
            lbl = tk.Label(self.canvas, text=navaid, bg=SCREEN_BG, fg=SCREEN_FG)
            lbl.place(x=x+5, y=y-5)

    def create_starter_aircraft(self):
        for callsign in EXERCISE["scenery"]["aircraft"]:
            ac = EXERCISE["scenery"]["aircraft"][callsign]
            self.blips[callsign] = Blip(x=(self.screen_lengths / 2) + nm2px(ac["xy_nm"][0]),
                                        y=(self.screen_lengths / 2) + nm2px(ac["xy_nm"][1]),
                                        hdg=ac["hdg"], kts=ac["kts"],
                                        callsign=callsign,
                                        altitude=ac["alt"], squawk=ac["squawk"],
                                        route=ac["route"],
                                        active_station=None,
                                        auto_draw_canvas=self.canvas)
        """
        # Conflict testing
        self.blips["10"] = Blip(300, 300, 90, 120, "GTEST", 3000, 7000, None, self.canvas)
        self.blips["11"] = Blip(310, 310, 360, 120, "GTESU", 3500, 7000, None, self.canvas)
        """

    def draw_controls(self):
        global PAUSED
        global CONTROLS
        CONTROLS = {"reset_display": {"text": "RESET DISPLAY",
                                      "bg": "#fc0",
                                      "command": reset_display},
                    "cs_ssr": {"text": DISPLAY["C/S_SSR"],
                               "bg": None,
                               "command": change_cs_sq},
                    "rings": {"text": "RINGS [ON/OFF]",
                              "bg": "auto",
                              "command": change_rings},
                    "lines": {"text": "LINES [ON/OFF]",
                              "bg": "auto",
                              "command": change_lines},
                    "crumbs": {"text": "CRUMBS [ON/OFF]",
                               "bg": "auto",
                               "command": change_crumbs},
                    "airspace": {"text": "CTA BOUNDARY [ON/OFF]",
                                 "bg": "auto",
                                 "command": change_airspace},
                    "extra_label": {"text": "EXTRA LABELS [ON/OFF]",
                                    "bg": "auto",
                                    "command": change_extra},
                    "est_alt_reach": {"text": "EST ALT REACH [ON/OFF]",
                                      "bg": "auto",
                                      "command": change_estalt},
                    "controlled": {"text": "UNCONTROLLED A/C [ON/OFF]",
                                    "bg": "auto",
                                    "command": change_controlled},
                    "rings_n": {"text": "INCREASE RINGS ([VALUE])",
                                  "bg": None,
                                  "command": rings_increase},
                    "rings_dec": {"text": "DECREASE RINGS",
                                  "bg": None,
                                  "command": rings_decrease},
                    "rings_d": {"text": "WIDER RINGS ([VALUE]nm)",
                                "bg": None,
                                "command": rings_wider},
                    "rings_thi": {"text": "THINNER RINGS",
                                  "bg": None,
                                  "command": rings_thinner},
                    "lines_m": {"text": "LINES MODE ([VALUE])",
                                "bg": None,
                                "command": lines_mode},
                    "lines_n": {"text": "LONGER LINES ([VALUE]"+("min" if DISPLAY["LINES_M"] == "Time" else "nm")+")",
                                "bg": None,
                                "command": lines_increase},
                    "lines_dec": {"text": "SHORTER LINES",
                                  "bg": None,
                                  "command": lines_decrease},
                    "cta_width": {"text": "WIDER BOUNDARY ([VALUE])",
                                  "bg": None,
                                  "command": cta_wider},
                    "cta_thi": {"text": "THINNER BOUNDARY",
                                "bg": None,
                                "command": cta_thinner}}
        global SIM_CONTROLS
        SIM_CONTROLS = {"pause": {"text": "RESUME" if PAUSED else "PAUSE",
                                  "bg": "lightblue" if PAUSED else "lightgreen",
                                  "command": change_pause},
                        "reset": {"text": "RESET SIM",
                                  "bg": "red",
                                  "command": reset_sim},
                        "sim_speed": {"text": "INCREASE SPEED",
                                      "bg": None,
                                      "command": speed_increase},
                        "speed_dec": {"text": "DECREASE SPEED",
                                      "bg": None,
                                      "command": speed_decrease},
                        "speed_reset": {"text": "RESET SPEED",
                                        "bg": None,
                                        "command": speed_reset},
                        "weather": {"text": "WEATHER [VALUE]",
                                    "bg": None,
                                    "command": change_weather}}
        
        self.visual_label = tk.Label(self.root, text=DISPLAY["VISUAL_LABEL"], padx=btn_padx(DISPLAY["VISUAL_LABEL"]))
        self.visual_label.place(x=5, y=10)
        
        y_val = 40
        y_step = 30
        for key in CONTROLS:
            info = CONTROLS[key]
            if "[ON/OFF]" in info["text"]:
                info["text"] = info["text"].replace("[ON/OFF]", "ON" if DISPLAY[key.upper()] else "OFF")
            elif "[VALUE]" in info["text"]:
                info["text"] = info["text"].replace("[VALUE]", str(DISPLAY[key.upper()]))
            if info["bg"] == "auto":
                info["bg"] = "lightgreen" if DISPLAY[key.upper()] else "lightgrey"
            setattr(self, key, tk.Button(self.root, text=info["text"], bg=info["bg"], command=info["command"], padx=btn_padx(info["text"])))
            getattr(self, key).place(x=5, y=y_val)
            y_val += y_step

        self.sim_label = tk.Label(self.root, text=DISPLAY["SIM_LABEL"], padx=btn_padx(DISPLAY["SIM_LABEL"]))
        self.sim_label.place(x=5, y=y_val)
        y_val += y_step

        for key in SIM_CONTROLS:
            info = SIM_CONTROLS[key]
            if "[ON/OFF]" in info["text"]:
                info["text"] = info["text"].replace("[ON/OFF]", "ON" if DISPLAY[key.upper()] else "OFF")
            elif "[VALUE]" in info["text"]:
                info["text"] = info["text"].replace("[VALUE]", str(DISPLAY[key.upper()]))
            if info["bg"] == "auto":
                info["bg"] = "lightgreen" if DISPLAY[key.upper()] else "lightgrey"
            setattr(self, key, tk.Button(self.root, text=info["text"], bg=info["bg"], command=info["command"], padx=btn_padx(info["text"])))
            getattr(self, key).place(x=5, y=y_val)
            y_val += y_step

        self.speed = tk.Label(self.root, text="Sim speed: "+str(float(DISPLAY["SIM_SPEED"]))+"x", bg=SCREEN_BG)
        self.speed.place(x=(self.master_width-self.screen_lengths) / 2, y=5)
        if DISPLAY["WEATHER"] == "OFF":
            lbl_txt = "N/A"
            weather_package = {}
        elif DISPLAY["WEATHER"] == "RANDOM":
            weather_package = randomWeather("EGDM")  # Auto req
            lbl_txt = weather_package["raw_text"]
        elif DISPLAY["WEATHER"] == "LIVE":
            weather_package = liveWeather("EGDM")  # Auto req
            lbl_txt = weather_package["raw_text"]
        DISPLAY["LIVE_WEATHER"] = weather_package
        self.metar = tk.Label(self.root, text="METAR: "+lbl_txt, bg=SCREEN_BG)
        self.metar.place(x=(self.master_width-self.screen_lengths) / 2, y=self.screen_lengths - 25)  # 25 is purely visual adjustment        


def btn_padx(text):
    global SCREEN
    master, screen = SCREEN
    desired = (master - screen) / 2
    length = font.nametofont("TkDefaultFont").measure(text)
    padx = (desired - length) / 2
    return padx - 10


def reset_sim():
    sim.clear()
    for callsign in EXERCISE["scenery"]["aircraft"]:
        ac = EXERCISE["scenery"]["aircraft"][callsign]
        sim.blips[callsign] = Blip(x=(sim.screen_lengths / 2) + nm2px(ac["xy_nm"][0]),
                                   y=(sim.screen_lengths / 2) + nm2px(ac["xy_nm"][1]),
                                   hdg=ac["hdg"], kts=ac["kts"],
                                   callsign=callsign,
                                   altitude=ac["alt"], squawk=ac["squawk"],
                                   route=ac["route"],
                                   active_station=None,
                                   auto_draw_canvas=sim.canvas, auto_draw=False)
    sim.draw()
    if not PAUSED:
        change_pause()

def reset_display():
    global DISPLAY
    global DISPLAY_OLD
    global CONTROLS
    DISPLAY = DISPLAY_OLD.copy()
    for key in CONTROLS:
        try:
            CONTROLS[key]["command"](False)
        except TypeError:
            continue
        except Exception as err:
            raise err

# CHANGE change_# FUNCTIONS INTO ONE
def change_weather(counter=True):
    options = ("OFF", "RANDOM", "LIVE")
    global DISPLAY
    if counter:
        i = options.index(DISPLAY["WEATHER"])
        i += 1
        try:
            DISPLAY["WEATHER"] = options[i]
        except IndexError:
            DISPLAY["WEATHER"] = options[0]
        except Exception as err:
            raise err
        if DISPLAY["WEATHER"] == "OFF":
            metar_txt = "N/A"
        elif DISPLAY["WEATHER"] == "RANDOM":
            weather_package = randomWeather("EGDM")  # Auto req
            metar_txt = weather_package["raw_text"]
        elif DISPLAY["WEATHER"] == "LIVE":
            weather_package = liveWeather("EGDM")  # Auto req
            metar_txt = weather_package["raw_text"]
    lbl_txt = "WEATHER " + DISPLAY["WEATHER"]
    sim.weather.configure(text=lbl_txt, padx=btn_padx(lbl_txt))
    sim.metar.configure(text="METAR: "+metar_txt)

def speed_increase(counter=True):
    global DISPLAY
    if counter: DISPLAY["SIM_SPEED"] += 0.5
    lbl_txt = "Sim speed: "+str(DISPLAY["SIM_SPEED"])+"x"
    sim.speed.configure(text=lbl_txt, bg=SCREEN_BG)

def speed_decrease(counter=True):
    global DISPLAY
    if counter: DISPLAY["SIM_SPEED"] -= 0.5
    if DISPLAY["SIM_SPEED"] < 0.5:
        DISPLAY["SIM_SPEED"] = 0.5
    lbl_txt = "Sim speed: "+str(DISPLAY["SIM_SPEED"])+"x"
    sim.speed.configure(text=lbl_txt, bg=SCREEN_BG)

def speed_reset(counter=True):
    global DISPLAY
    if counter: DISPLAY["SIM_SPEED"] = 1
    lbl_txt = "Sim speed: 1.0x"
    sim.speed.configure(text=lbl_txt, bg=SCREEN_BG)

def change_lines(counter=True):
    global DISPLAY
    if counter: DISPLAY["LINES"] = not DISPLAY["LINES"]
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "LINES " + ("ON" if DISPLAY["LINES"] else "OFF")
    sim.lines.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["LINES"] else "lightgrey")

def lines_mode(counter=True):
    global DISPLAY
    if DISPLAY["LINES_M"] == "Time" and counter:
        DISPLAY["LINES_M"] = "Dist"
    elif counter:
        DISPLAY["LINES_M"] = "Time"
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "LINES MODE (" + DISPLAY["LINES_M"] + ")"
    sim.lines_m.configure(text=lbl_txt, padx=btn_padx(lbl_txt))
    lbl_txt = "LONGER LINES (" + str(DISPLAY["LINES_N"]) + ("min" if DISPLAY["LINES_M"] == "Time" else "nm") + ")"
    sim.lines_n.configure(text=lbl_txt, padx=btn_padx(lbl_txt))
    
def lines_increase(counter=True):
    global DISPLAY
    if counter: DISPLAY["LINES_N"] += 1
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "LONGER LINES (" + str(DISPLAY["LINES_N"]) + ("min" if DISPLAY["LINES_M"] == "Time" else "nm") + ")"
    sim.lines_n.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def lines_decrease(counter=True):
    global DISPLAY
    if counter: DISPLAY["LINES_N"] -= 1
    if DISPLAY["LINES_N"] <= 0:
        DISPLAY["LINES_N"] = 1
    else:
        for blip_id in sim.blips:
            sim.blips[blip_id].clear(sim.canvas)
            sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "LONGER LINES (" + str(DISPLAY["LINES_N"]) + ("min" if DISPLAY["LINES_M"] == "Time" else "nm") + ")"
    sim.lines_n.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def cta_wider(counter=True):
    global DISPLAY
    if counter: DISPLAY["CTA_WIDTH"] += 1
    for airport_id in sim.airports:
        if airport_id == sim.master_airport:
            sim.airports[airport_id].clear(sim.canvas)
            sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "WIDER BOUNDARY (" + str(DISPLAY["CTA_WIDTH"]) + ")"
    sim.cta_width.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def cta_thinner(counter=True):
    global DISPLAY
    if counter: DISPLAY["CTA_WIDTH"] -= 1
    if DISPLAY["CTA_WIDTH"] <= 0:
        DISPLAY["CTA_WIDTH"] = 1
    else:
        for airport_id in sim.airports:
            if airport_id == sim.master_airport:
                sim.airports[airport_id].clear(sim.canvas)
                sim.airports[airport_id].draw(sim.canvas)

def rings_increase(counter=True):
    global DISPLAY
    if counter: DISPLAY["RINGS_N"] += 1
    for airport_id in sim.airports:
        if airport_id == sim.master_airport:  # Rings only on master airport
            sim.airports[airport_id].clear(sim.canvas)
            sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "INCREASE RINGS (" + str(DISPLAY["RINGS_N"]) + ")"
    sim.rings_n.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def rings_decrease(counter=True):
    global DISPLAY
    if counter: DISPLAY["RINGS_N"] -=1
    if DISPLAY["RINGS_N"] <= 0:
        DISPLAY["RINGS_N"] = 1
    else:
        for airport_id in sim.airports:
            if airport_id == sim.master_airport:
                sim.airports[airport_id].clear(sim.canvas)
                sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "INCREASE RINGS (" + str(DISPLAY["RINGS_N"]) + ")"
    sim.rings_n.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def rings_wider(counter=True):
    global DISPLAY
    if counter: DISPLAY["RINGS_D"] += 5
    for airport_id in sim.airports:
        if airport_id == sim.master_airport:
            sim.airports[airport_id].clear(sim.canvas)
            sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "WIDER RINGS (" + str(DISPLAY["RINGS_D"]) + "nm)"
    sim.rings_d.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def rings_thinner(counter=True):
    global DISPLAY
    if counter: DISPLAY["RINGS_D"] -= 5
    if DISPLAY["RINGS_D"] < 5:
        DISPLAY["RINGS_D"] = 5
    else:
        for airport_id in sim.airports:
            if airport_id == sim.master_airport:
                sim.airports[airport_id].clear(sim.canvas)
                sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "WIDER RINGS (" + str(DISPLAY["RINGS_D"]) + "nm)"
    sim.rings_d.configure(text=lbl_txt, padx=btn_padx(lbl_txt))

def change_estalt(counter=True):
    global DISPLAY
    if counter: DISPLAY["EST_ALT_REACH"] = not DISPLAY["EST_ALT_REACH"]
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "EST ALT REACH "+("ON" if DISPLAY["EST_ALT_REACH"] else "OFF")
    sim.est_alt_reach.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["EST_ALT_REACH"] else "lightgrey")


def change_airspace(counter=True):
    global DISPLAY
    if counter: DISPLAY["AIRSPACE"] = not DISPLAY["AIRSPACE"]
    for airport_id in sim.airports:
        sim.airports[airport_id].clear(sim.canvas)
        sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "CTA BOUNDARY "+("ON" if DISPLAY["AIRSPACE"] else "OFF")
    sim.airspace.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["AIRSPACE"] else "lightgrey")


def change_controlled(counter=True):
    global DISPLAY
    if counter: DISPLAY["CONTROLLED"] = not DISPLAY["CONTROLLED"]
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "UNCONTROLLED A/C "+("ON" if DISPLAY["CONTROLLED"] else "OFF")
    sim.controlled.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["CONTROLLED"] else "lightgrey")


def change_extra(counter=True):
    global DISPLAY
    if counter: DISPLAY["EXTRA_LABEL"] = not DISPLAY["EXTRA_LABEL"]
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "EXTRA LABELS "+("ON" if DISPLAY["EXTRA_LABEL"] else "OFF")
    sim.extra_label.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["EXTRA_LABEL"] else "lightgrey")


def change_cs_sq(counter=True):
    global DISPLAY
    if DISPLAY["C/S_SSR"] == "C/S" and counter:
        DISPLAY["C/S_SSR"] = "SSR"
    elif counter:
        DISPLAY["C/S_SSR"] = "C/S"
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    sim.cs_ssr.configure(text=DISPLAY["C/S_SSR"], padx=btn_padx(DISPLAY["C/S_SSR"]))


def change_rings(counter=True):
    global DISPLAY
    if counter: DISPLAY["RINGS"] = not DISPLAY["RINGS"]
    for airport_id in sim.airports:
        sim.airports[airport_id].clear(sim.canvas)
        sim.airports[airport_id].draw(sim.canvas)
    lbl_txt = "RINGS "+("ON" if DISPLAY["RINGS"] else "OFF")
    sim.rings.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["RINGS"] else "lightgrey")


def change_crumbs(counter=True):
    global DISPLAY
    if counter: DISPLAY["CRUMBS"] = not DISPLAY["CRUMBS"]
    for blip_id in sim.blips:
        sim.blips[blip_id].clear(sim.canvas)
        sim.blips[blip_id].draw(sim.canvas, move=False)
    lbl_txt = "CRUMBS "+("ON" if DISPLAY["CRUMBS"] else "OFF")
    sim.crumbs.configure(text=lbl_txt, padx=btn_padx(lbl_txt), bg="lightgreen" if DISPLAY["CRUMBS"] else "lightgrey")


def change_pause(counter=True):
    global PAUSED
    if counter: PAUSED = not PAUSED
    if PAUSED:
        label_text = "RESUME"
    else:
        label_text = "PAUSE"
    sim.pause.configure(text=label_text, padx=btn_padx(label_text), bg="lightblue" if PAUSED else "lightgreen")


def tick():
    if not PAUSED:
        for blip_id in sim.blips:
            """ NOT DETECTING CONFLICTS
            for b_id in sim.blips:
                if blip_id == b_id: continue
                b1 = sim.blips[blip_id]
                b2 = sim.blips[b_id]
                h = pointInCircle(b1.x, b1.y, b2.x, b2.y, nm2px(3))  # 3nm horizontal radius
                if h == True:  # If within 3nm of blip
                    highest_alt = b2.altitude if b2.altitude > b1.altitude else b1.altitude
                    other_alt = b2.altitude if highest_alt == b1.altitude else b1.altitude
                    alt_diff = highest_alt - other_alt
                    if alt_diff < 1000:
                        b2.conflicting = True
                        b1.conflicting = True
                else:
                    b2.conflicting = False
                    b1.conflicting = False
            """
            sim.blips[blip_id].clear(sim.canvas)
            sim.blips[blip_id].draw(sim.canvas)
        if DISPLAY["TICKED"]:
            print("Ticked")
    sim.root.after(int(TICK_DURATION / DISPLAY["SIM_SPEED"]), tick)


if __name__ == "__main__":
    print("Running...")
    sim = Sim(tk.Tk(), TITLE)
    sim.root.after(int(TICK_DURATION / DISPLAY["SIM_SPEED"]), tick)
    print("Loaded tick", TICK_DURATION, str(DISPLAY["SIM_SPEED"])+"x")
    sim.root.mainloop()