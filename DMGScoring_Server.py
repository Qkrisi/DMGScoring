from flask import Flask, request
import json
import DMGScoring
from os import path

class Encoder(json.JSONEncoder):
	def default(self, o):
		return o.__dict__

app = Flask("DMGScoring")

HOST = ""
PORT = 0
TABLE_ENDPOINT = ""

with open("config.json", "r") as f:
	data = json.loads("\n".join(f.readlines()))
	HOST = data["Host"]
	PORT = data["Port"]
	TABLE_ENDPOINT = data["TableEndpoint"]

@app.errorhandler(DMGScoring.DMGException)
def HandleError(e):
	return f"Error: {str(e)}", 200

def readFromStatic(_path = "index.html", _separator = "", **variables) -> str:
	if not path.isfile(f"./static/{_path}"):return "Invalid path"
	with open(f"./static/{_path}","r") as f:
		content = f.readlines()
	base = _separator.join(content)
	for variable in variables:base = base.replace(f'{"{"}{"{"}{variable}{"}"}{"}"}', str(variables[variable]))
	return base

HomeValue = """
	<html>
		<head>
			<style>
				textarea{
					width: 900px;
					height: 500px;
					resize: none;
				}
			</style>
		</head>
		<body>
			<form id="dmgform" action="
	"""+ f"""{TABLE_ENDPOINT}" method="post">
				<textarea name="DMG" placeholder="DMG string"></textarea>
				<br>
				<input type="submit">
			</form>
		</body>
	</html>"""

@app.route("/")
def home():
	return HomeValue

@app.route("/table", methods=["POST"])
def table():
	data = request.form.to_dict(flat=False)
	if not data:
		data = request.json["form"]
	DMGString = data["DMG"][0]
	Mission = DMGScoring.ParseDMG(DMGString)
	Totals = Mission["Total"]
	Pools = ""
	for pool in Mission["Modules"]:
		Pools+="<tr>"
		Pools+=f'<th class="color2">{pool.N}</th>'
		Pools+=f'<th class="color3">{str(pool)}</th>'
		Pools+=f'<th class="color4">{"-" if pool.AveragePoints == 0 else pool.AveragePoints}</th>'
		Pools+=f'<th class="color5">{"-" if pool.TotalPoints == 0 else pool.TotalPoints}</th>'
		Pools+=f'<th class="color6">{"-" if pool.Time == "00:00:00" else pool.Time}</th>'
		Pools+="</tr>"
	HTMLData = {
		"MissionHead": "<br>".join(f"{key}: {Mission[key]}" for key in Mission if key not in ["Total", "Modules"])+"</b>",
		"TotalData": f'{Totals["ModuleCount"]} Modules total<br>Points per module: {Totals["PointsPerModule"]}<br>Points per minute: {Totals["PointsPerMinute"]}',
		"TotalPoints": Totals["Points"],
		"TotalTime": Totals["Time"],
		"Pools": Pools
	}
	return readFromStatic("table.html", **HTMLData)
	

@app.route("/api", methods=["POST"])
def api():
	return json.dumps(DMGScoring.ParseDMG(request.json["DMG"]), cls=Encoder)

app.run(host=HOST, port=PORT)
