import re
import urllib.request
import json
import math

class DMGException(Exception):pass

ScoreURL = ""
RawJSON = ""

with open("config.json", "r") as f:
	data = json.loads("\n".join(f.readlines()))
	ScoreURL = data["ScoreURL"]
	RawJSON = data["RawURL"]

ScorePriority = {
	"Assigned Score":"Assigned",
	"Assigned Total boss points earned (adjust # of modules)":"Assigned boss points",
	"Community Score":"Community",
	"Community Boss Score":"Community boss points",
	"TP\nScore":"TP",
	"TP\nTotal boss points earned (adjust # of modules)":"TP boss points",
	"Resolved Score":"Score",
	"Total Resolved Points per Module Rounded":"Boss points"
	
}

PPMPriority = [
	"Assigned per module",
	"Community Per Module",
	"Resolved Boss Points per Module"
]

VANILLA_AVERAGE = 2.36

LineTypes = {
	r"^\/\/\/\/ (.*?)$": "Mission",
	r"^\/\/\/ (.*?)$": "Description",
	r"^((\d+):)?(\d+):(\d+)$": "Time",
	r"^(\d+)X$": "Strikes",
	r"^!?((\d+)\s?\*\s?)?(.*?)$": "Modules"
}

class Module:
	def __init__(self, name, base, BaseName, ppm, color):
		self.Name = name
		self.BaseName = BaseName
		self.Multiplier = 1
		self.Color = color
		self.BaseScore = base
		self.PPM = ppm
		self.Special = self.Color == "blue"
		if ppm > 0:
			self.Color = "red"
		if not self.Special and self.BaseScore == 0:
			self.BaseScore = 10
			self.BaseName = "Default"
	
	def __str__(self):
		Inner = f"{self.Name}"
		if self.Multiplier > 1:
			Inner+=f" (x{self.Multiplier})"
		if not self.Special:
			Inner += f" - {self.BaseScore}"
			if self.PPM > 0:
				Inner += f" + {self.PPM} PPM"
			Inner += f" ({self.BaseName})"
		return f'<span style="color:{self.Color}">{Inner}</span>'
	
class Pool:
	def __init__(self, n, modules, GetRecord):
		self.N = n
		self.Modules = modules
		self.Scores = {}
		for m in modules:
			if m in self.Scores:
				self.Scores[m].Multiplier += 1
			elif m in ["ALL_SOLVABLE", "ALL_MODS"]:
				self.Scores[m] = Module(m, 10, "Default", 0, "deeppink")
			elif m in ["ALL_NEEDY", "ALL_VANILLA_NEEDY", "ALL_MODS_NEEDY"]:
				self.Scores[m] = Module(m, 0, "Default", 0, "deeppink")
			elif m == "ALL_VANILLA":
				self.Scores[m] = Module(m, VANILLA_AVERAGE, "Default", 0, "deeppink")
			else:
				record = GetRecord(m)
				if isinstance(record, str):
					self.Scores[m] = Module(record, 0, "Default", 0, "blue")
				else:
					self.Scores[m] = Module(record["Module Name"], *ReadPriority(record, ScorePriority), ReadPriority(record, PPMPriority)[0], "black")
		self.ScoreValues = tuple(self.Scores.values())
	
	def Calculate(self, count, CurrentSeconds):
		self.AveragePoints = round(sum((module.BaseScore+module.PPM*count)*module.Multiplier for module in self.ScoreValues)/len(self.Modules), 2)
		self.TotalPoints = self.AveragePoints*self.N
		seconds = normal_round(self.TotalPoints*7.5)
		self.Time = GetTime(seconds)
		return CurrentSeconds + seconds
	
	def __str__(self):
		return "<br>".join(str(module) for module in self.ScoreValues)

def FormatTime(n):
		n = str(n)
		if len(n) == 1:
			n = "0" + n
		return n

def GetTime(allseconds):
	seconds = allseconds%60
	minutes = (allseconds-seconds)%3600//60
	hours = (allseconds-minutes*60)//3600
	seconds = FormatTime(seconds)
	minutes = FormatTime(minutes)
	hours = FormatTime(hours)
	return f"{hours}:{minutes}:{seconds}"

def normal_round(n):
		fl = math.floor(n)
		if n - fl < 0.5:
			return fl
		return math.ceil(n)


def ReadPriority(record, priorities):
	for key in priorities:
		if not key in record:
			continue
		value = record[key]
		if not str(value).strip():
			continue
		return value, priorities[key] if isinstance(priorities, dict) else "Default"
	return 0, "Default"

def ParseDMG(DMGString):

	splitted = DMGString.split("\n")

	Mission = {"Total":{}}

	ScoreDump = []

	RawModules = []

	with urllib.request.urlopen(ScoreURL) as url:
		ScoreDump = json.loads(url.read().decode())
		del ScoreDump[0]
		
	with urllib.request.urlopen(RawJSON) as url:
		RawModules = json.loads(url.read().decode())["KtaneModules"]


	def GetRecordByID(module):
		for record in ScoreDump:
			if record["ModuleID"] == module:
				return record
		for m in RawModules:
			if m["ModuleID"] == module:
				return m["Name"]
		raise DMGException(f"Invalid module ID: {module}")
					
	ModuleCount = 0

	for line in splitted:
		line = line.strip()
		if not line:
			continue
		for regex in LineTypes:
			match = re.search(regex, line)
			if match!=None:
				field = LineTypes[regex]
				if field == "Time":
					timesplit = tuple(map(int, match.string.split(":")))
					allseconds = timesplit[0]*3600+timesplit[1]*60+timesplit[2] if len(timesplit)==3 else timesplit[0]*60+timesplit[1]
					if allseconds <= 0:
						raise DMGException("The number of seconds cannot be 0 or less.")
					Mission["Time"] = GetTime(allseconds)
				elif ":" in line:
					break
				elif field == "Modules":
					if not "Modules" in Mission:
						Mission["Modules"] = []
					n = match.group(2)
					num = int(n) if n else 1
					ModuleCount+=num
					Mission["Modules"].append(Pool(num, [m.strip() for m in match.group(3).split(",")], GetRecordByID))
				else:
					Mission[field] = match.group(1)
				break
	AllSeconds = 0
	
	if not "Modules" in Mission:
		raise DMGException("No modules specified")

	for pool in Mission["Modules"]:
		AllSeconds = pool.Calculate(ModuleCount, AllSeconds)
	
	TotalPoints = sum(pool.TotalPoints for pool in Mission["Modules"])
	Mission["Total"]["Time"]=GetTime(AllSeconds)
	Mission["Total"]["Points"] = TotalPoints
	Mission["Total"]["ModuleCount"] = ModuleCount
	Mission["Total"]["PointsPerMinute"] = round(60/TotalPoints, 2)
	Mission["Total"]["PointsPerModule"] = round(TotalPoints/ModuleCount, 2)
	
	return Mission
