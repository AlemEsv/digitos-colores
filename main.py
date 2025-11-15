import tempfile
import os
from flask import Flask, request, redirect, send_file
from skimage import io
import base64
import glob
import numpy as np
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

main_html = """
<html>
<head></head>
<script>
  var mousePressed = false;
  var lastX, lastY;
  var ctx;

   function getRndInteger(min, max) {
    return Math.floor(Math.random() * (max - min) ) + min;
   }

  function InitThis() {
      ctx = document.getElementById('myCanvas').getContext("2d");

      // Generar un número aleatorio del 0 al 9
      numero = getRndInteger(0, 10);
      
      document.getElementById('mensaje').innerHTML  = 'Dibuja el número: ' + numero;
      document.getElementById('numero').value = numero;
      
      // Generar un color aleatorio
      var colores = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan', 'magenta', 'lime'];
      var colorAleatorio = colores[Math.floor(Math.random() * colores.length)];
      document.getElementById('colorActual').value = colorAleatorio;
      document.getElementById('colorInfo').innerHTML = 'Color: ' + colorAleatorio;

      $('#myCanvas').mousedown(function (e) {
          mousePressed = true;
          Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, false);
      });

      $('#myCanvas').mousemove(function (e) {
          if (mousePressed) {
              Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, true);
          }
      });

      $('#myCanvas').mouseup(function (e) {
          mousePressed = false;
      });
  	    $('#myCanvas').mouseleave(function (e) {
          mousePressed = false;
      });
  }

  function Draw(x, y, isDown) {
      if (isDown) {
          ctx.beginPath();
          var colorActual = document.getElementById('colorActual').value;
          ctx.strokeStyle = colorActual;
          ctx.lineWidth = 11;
          ctx.lineJoin = "round";
          ctx.moveTo(lastX, lastY);
          ctx.lineTo(x, y);
          ctx.closePath();
          ctx.stroke();
      }
      lastX = x; lastY = y;
  }

  function clearArea() {
      // Use the identity matrix while clearing the canvas
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  }

  //https://www.askingbox.com/tutorial/send-html5-canvas-as-image-to-server
  function prepareImg() {
     var canvas = document.getElementById('myCanvas');
     document.getElementById('myImage').value = canvas.toDataURL();
  }



</script>
<body onload="InitThis();">
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js" type="text/javascript"></script>
    <script type="text/javascript" ></script>
    <div align="center">
        <h1 id="mensaje">Dibujando...</h1>
        <h2 id="colorInfo" style="margin: 10px;">Color: </h2>
        <canvas id="myCanvas" width="200" height="200" style="border:2px solid black"></canvas>
        <br/>
        <br/>
        <button onclick="javascript:clearArea();return false;">Borrar</button>
    </div>
    <div align="center">
      <form method="post" action="upload" onsubmit="javascript:prepareImg();"  enctype="multipart/form-data">
      <input id="numero" name="numero" type="hidden" value="">
      <input id="colorActual" name="colorActual" type="hidden" value="">
      <input id="myImage" name="myImage" type="hidden" value="">
      <input id="bt_upload" type="submit" value="Enviar">
      </form>
    </div>
</body>
</html>

"""

@app.route("/")
def main():
    return(main_html)

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # check if the post request has the file part
        img_data = request.form.get('myImage').replace("data:image/png;base64,","")
        aleatorio = request.form.get('numero')
        print(f"Guardando dígito: {aleatorio}")
        
        # Crear carpeta si no existe
        digit_folder = os.path.join(os.getcwd(), str(aleatorio))
        if not os.path.exists(digit_folder):
            os.makedirs(digit_folder, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(delete=False, mode="w+b", suffix='.png', dir=digit_folder) as fh:
            fh.write(base64.b64decode(img_data))
    except Exception as err:
        print("Error occurred")
        print(err)

    return redirect("/", code=302)


@app.route('/commit', methods=['GET'])
def commit_to_github():
    try:
        import requests
        import json
        from datetime import datetime
        
        # Obtener token de las variables de entorno
        github_token = os.environ.get('GITHUB_TOKEN')
        
        if not github_token:
            return "Error: token no configurado.<br><a href='/'>Volver</a>"
        
        repo_owner = "AlemEsv"
        repo_name = "digitos-colores"
        
        headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Obtener el SHA del último commit en main
        ref_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads/main'
        ref_response = requests.get(ref_url, headers=headers)
        
        if ref_response.status_code != 200:
            return f"Error al obtener referencia: {ref_response.text}<br><a href='/'>Volver</a>"
        
        last_commit_sha = ref_response.json()['object']['sha']
        
        # Obtener el tree del último commit
        commit_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits/{last_commit_sha}'
        commit_response = requests.get(commit_url, headers=headers)
        base_tree_sha = commit_response.json()['tree']['sha']
        
        # Crear blobs y tree para las imágenes
        tree_items = []
        image_count = 0
        
        for digit in range(10):
            digit_folder = os.path.join(os.getcwd(), str(digit))
            if os.path.exists(digit_folder):
                for img_file in glob.glob(os.path.join(digit_folder, '*.png')):
                    with open(img_file, 'rb') as f:
                        content = base64.b64encode(f.read()).decode('utf-8')
                    
                    # Crear blob
                    blob_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/blobs'
                    blob_data = {
                        'content': content,
                        'encoding': 'base64'
                    }
                    blob_response = requests.post(blob_url, headers=headers, json=blob_data)
                    
                    if blob_response.status_code == 201:
                        blob_sha = blob_response.json()['sha']
                        file_name = os.path.basename(img_file)
                        tree_items.append({
                            'path': f'{digit}/{file_name}',
                            'mode': '100644',
                            'type': 'blob',
                            'sha': blob_sha
                        })
                        image_count += 1
        
        if image_count == 0:
            return "No hay imágenes nuevas para subir.<br><a href='/'>Volver</a>"
        
        # Crear tree
        tree_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/trees'
        tree_data = {
            'base_tree': base_tree_sha,
            'tree': tree_items
        }
        tree_response = requests.post(tree_url, headers=headers, json=tree_data)
        
        if tree_response.status_code != 201:
            return f"Error al crear tree: {tree_response.text}<br><a href='/'>Volver</a>"
        
        new_tree_sha = tree_response.json()['sha']
        
        # Crear commit
        new_commit_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/commits'
        commit_data = {
            'message': f'Upload images',
            'tree': new_tree_sha,
            'parents': [last_commit_sha]
        }
        new_commit_response = requests.post(new_commit_url, headers=headers, json=commit_data)
        
        if new_commit_response.status_code != 201:
            return f"Error al crear commit<br><a href='/'>Volver</a>"
        
        new_commit_sha = new_commit_response.json()['sha']
        
        # Actualizar la referencia main
        update_ref_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads/main'
        update_data = {
            'sha': new_commit_sha,
            'force': False
        }
        update_response = requests.patch(update_ref_url, headers=headers, json=update_data)
        
        if update_response.status_code == 200:
            return f"<a href='/'>Continuar dibujando</a>"
        else:
            return f"Error al actualizar<br><a href='/'>Volver</a>"
            
    except Exception as e:
        return f"Error: {str(e)}<br><a href='/'>Volver</a>"

if __name__ == "__main__":
    # Crear carpetas para los dígitos del 0 al 9
    for d in range(10):
        digit_folder = os.path.join(os.getcwd(), str(d))
        if not os.path.exists(digit_folder):
            os.makedirs(digit_folder, exist_ok=True)
    
    # Configuración para Railway
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)