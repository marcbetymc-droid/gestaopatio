import pandas as pd
from flask import Flask
from flask import render_template, redirect, url_for, flash, request, jsonify, Blueprint, current_app
from gestaopatio.foms import FormCriarConta, FormLogin, FormAgendamentos, FormReagenda, FormFrota, FormCliente, FormEmbarcador, FormFrotaTerceiro, FormMotorista, FormControlPatio, FormControlFaixa 
from datetime import date, datetime, time, timezone, timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, DateField, DateTimeField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_bcrypt import Bcrypt as bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_wtf.file import FileField, FileAllowed
import pytz
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func
from gestaopatio import database, bcrypt
from zoneinfo import ZoneInfo


bp = Blueprint('main', __name__)


@bp.route('/')
def home():
    from gestaopatio.models import Agendamentos
    cache = current_app.extensions['cache']
    resultado = cache.get('home_page')
    if resultado:
        return resultado

    lista_cargas = Agendamentos.query.filter(
        Agendamentos.status_carga == None
    ).order_by(Agendamentos.entrydate, Agendamentos.entryhour).all()

    resultado = render_template('Home.html', lista_cargas=lista_cargas)
    cache.set('home_page', resultado, timeout=120)
    return resultado

    
@bp.route('/painel')
def painel():
    from gestaopatio.models import Agendamentos
    cache = current_app.extensions['cache']
    resultado1 = cache.get('painel_page')
    if resultado1:
        return resultado1   
    lista_cargas = Agendamentos.query.filter(
        Agendamentos.status_carga == None,
        Agendamentos.saida_portaria == None
    ).order_by(Agendamentos.entrydate, Agendamentos.entryhour).all()

    tz_sp = ZoneInfo("America/Sao_Paulo")  # Fuso horário de São Paulo
    resultado1 = render_template('Painel Cargas.html', lista_cargas=lista_cargas, tz_sp=tz_sp)
    cache.set('painel_page', resultado1, timeout=120)
    return resultado1
       
@bp.route('/painel_acompanha')
def painel_acompanha():
    from gestaopatio.models import Agendamentos
    cache = current_app.extensions['cache']
    resultado2 = cache.get('painel_acompanha_page')
    if resultado2:
        return resultado2       
    lista_cargas = Agendamentos.query.filter(Agendamentos.status_carga == None).order_by(Agendamentos.entrydate, Agendamentos.entryhour).all()
    tz_sp = ZoneInfo("America/Sao_Paulo")  # Fuso horário de São Paulo
    resultado2 = render_template('Painel Carga.html', lista_cargas=lista_cargas, tz_sp=tz_sp)
    cache.set('painel_acompanha_page', resultado2, timeout=120)
    return resultado2
       
@bp.route('/painel_produtos')
def painel_produtos():
    from gestaopatio.models import Agendamentos
    cache = current_app.extensions['cache']
    resultado3 = cache.get('painel_produtos_page')
    if resultado3:
        return resultado3       
    vendas = Vendas_ME.query.all()
    cargas = Agendamentos.query.all()
    
    lista_carga = {Agendamentos.num_transporte: Agendamentos for Agendamentos in cargas}
    csrf_token = generate_csrf()
    resultado3 = render_template('Painel Produtos.html', vendas=vendas, lista_carga = lista_carga, csrf_token=csrf_token)
    cache.set('painel_produtos_page', resultado3, timeout=120)
    return resultado3


@bp.route('/atualizar_gnre', methods=['POST'])
def atualizar_gnre():
    try:
        data = request.get_json()

        venda_id = data.get('id')
        guia_gnre = data.get('guia_gnre')

        venda = Vendas_ME.query.get(venda_id)
        if not venda:
            return jsonify({'success': False, 'error': 'Venda não encontrada'}), 404

        venda.guia_gnre = guia_gnre
        database.session.commit()
        return jsonify({'success': True})

    except SQLAlchemyError as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/painel_rota')
def painel_rota():
    from gestaopatio.models import Control_Patio
    cache = current_app.extensions['cache']
    resultado4 = cache.get('painel_rota_page')
    if resultado3:
        return resultado4          
    lista_patio = Control_Patio.query.filter(Control_Patio.hora_conclusao == None).order_by(Control_Patio.num_doca).all()
    #lista_patio = Control_Patio.query.filter(Control_Patio.num_frota == '1057').order_by(Control_Patio.num_doca).all()
    #lista_patio = Control_Patio.query.filter(Control_Patio.status_frota == 'Carregando').order_by(Control_Patio.num_doca).all()  
    for controle in lista_patio:
        num_transporte = controle.num_transporte
        controle.total_paletes = database.session.query(
            database.func.count(database.distinct(ControlPicking.num_palete))
        ).filter(
            ControlPicking.num_transporte == num_transporte,
            ControlPicking.conf_piso.is_(None),
            ControlPicking.tipo_palete == 'PICKING'
        ).scalar()
    
    resultado4 = render_template('Controle Patio.html', lista_patio=lista_patio)
    cache.set('painel_rota_page', resultado4, timeout=120)
    return resultado4

@bp.route('/stage_in')
def stage_in():
    from gestaopatio.models import Control_Patio
    lista_patio = Control_Patio.query.filter(
        Control_Patio.num_doca.isnot(None),
        Control_Patio.num_frota.isnot(None),
        Control_Patio.status_frota != 'Finalizada',
        Control_Patio.status_frota != 'Patio'
    ).all()

    def num_frota_int(item):
        try:
            return int(item.num_frota)
        except (TypeError, ValueError):
            return float('inf')

    lista_patio_ordenada = sorted(lista_patio, key=num_frota_int)

    # Docas ocupadas com status Stage ou Carregando
    docas_ocupadas = [
        int(item.num_doca)
        for item in lista_patio_ordenada
        if item.status_frota in ['Stage', 'Faixa', 'Carregando'] and item.num_doca is not None
    ]

    # Gerar lista de Stages disponíveis (por exemplo, de 1 a 999)
    stage_disponiveis = [i for i in range(1, 1000) if i not in docas_ocupadas]

    return render_template(
        'Cargas Stage_In.html',
        lista_patio=lista_patio_ordenada,
        stage_disponiveis=stage_disponiveis
    )

@bp.route('/update_content')
def update_content():
    from gestaopatio.models import Control_Patio
    # Consulta os registros válidos
    lista_patio = Control_Patio.query.filter(
        Control_Patio.num_doca.isnot(None),
        Control_Patio.num_frota.isnot(None),
        Control_Patio.status_frota != 'Finalizada',
        Control_Patio.status_frota != 'Patio',
        Control_Patio.num_frota != '704'   
    ).all()

    # Ordena pela num_frota convertida para inteiro
    def num_frota_int(item):
        try:
            return int(item.num_frota)
        except (TypeError, ValueError):
            return float('inf')

    lista_patio_ordenada = sorted(lista_patio, key=num_frota_int)

    # Filtra docas ocupadas com status Stage ou Carregando
    docas_ocupadas = [
        int(item.num_doca)
        for item in lista_patio_ordenada
        if item.status_frota in ['Stage', 'Faixa', 'Carregando'] and item.num_doca is not None
    ]

    # Gera lista de Stages disponíveis (por exemplo, de 1 a 999)
    stage_disponiveis = [i for i in range(1, 1000) if i not in docas_ocupadas]

    return render_template(
        'Cargas Stage_In-Atualizar.html',
        lista_patio=lista_patio_ordenada,
        stage_disponiveis=stage_disponiveis
    )

@bp.route('/painel_patio')
def painel_patio():
     from gestaopatio.models import Control_Patio
     lista_patio = Control_Patio.query.filter(Control_Patio.hora_conclusao == None).all()
     return render_template('Controle Patio.html', lista_patio=lista_patio)

@bp.route('/gestao_patio')
def gestao_patio():
     from gestaopatio.models import Control_Patio
     lista_patio = Control_Patio.query.filter(Control_Patio.hora_conclusao == None).all()
     return render_template('Gestão Faixa.html', lista_patio=lista_patio)


@bp.route('/lista_arquivos', methods=['GET'])
def lista_arquivos():
    from gestaopatio.models import Arquivos
    try:
        # Consulta todos os registros da tabela Arquivos
        lista_arquivos = Arquivos.query.order_by(Arquivos.ultima_alteracao.desc()).all()
        
        # Renderiza o template com os dados
        return render_template('Arq_Agendamento.html', lista_arquivos=lista_arquivos)
        
    except Exception as e:
        # Em caso de erro, exibe uma mensagem e redireciona
        flash(f'Ocorreu um erro ao carregar os arquivos: {str(e)}', 'alert-danger')
        return redirect(url_for('arq_produtos'))

@bp.route('/gestao_picking')
def gestao_picking():
    control_patio_id = request.args.get('control_patio_id', type=int)
    controle_patio = Control_Patio.query.get_or_404(control_patio_id)
    num_transporte = controle_patio.num_transporte
     
    separacao = database.session.query(
        ControlPicking.data_doc,
        ControlPicking.num_palete,
        ControlPicking.material,
        ControlPicking.descricao,
        ControlPicking.num_posicao,
        ControlPicking.pickeador,
        ControlPicking.tipo_palete,
        ControlPicking.num_transporte,
        ControlPicking.hora_confirmacao,
        database.func.sum(ControlPicking.qtd_remessa).label('total_qtd_remessa')
    ).filter(
        ControlPicking.num_transporte == num_transporte,
        ControlPicking.conf_piso.is_(None),
        ControlPicking.tipo_palete == 'PICKING'
    ).group_by(
        ControlPicking.data_doc,
        ControlPicking.num_palete,
        ControlPicking.material,
        ControlPicking.descricao,
        ControlPicking.num_posicao,
        ControlPicking.pickeador,
        ControlPicking.tipo_palete,
        ControlPicking.num_transporte,
        ControlPicking.hora_confirmacao
    ).all()
    
    if not separacao:
        flash('Transporte não encontrado.', 'alert-danger')
        return redirect(url_for('painel_rota'))
    
    current_time = datetime.now()
    return render_template('Painel Picking.html', controle_patio=controle_patio, separacao=separacao, now=current_time)

    
@bp.route('/lista_picking')
def lista_picking():
    from gestaopatio.models import ControlPicking
    lista_picking = ControlPicking.query.all()
    total_qtd_remessa = sum(int(picking.qtd_remessa) for picking in lista_picking if picking.qtd_remessa.isdigit())
    return render_template('Lista Picking.html', lista_picking=lista_picking, total_qtd_remessa=total_qtd_remessa)


@bp.route('/perfil')
@login_required
def perfil():
       foto_perfil=url_for('static', filename='fotos_perfil/koandina.jpg')
       return render_template('Perfil.html', foto_perfil=foto_perfil)
    
@bp.route('/perfil_moto')
@login_required
def perfil_moto():
       form_moto = FormMotorista()
       foto_motorista=url_for('static', filename='fotos_perfil/koandina.jpg')
       return render_template('Perfil_Motorista.html', foto_motorista=foto_motorista)

@bp.route('/graficos')
@login_required
def graficos():
       foto_perfil=url_for('static', filename='fotos_perfil/koandina.jpg')
       return render_template('Gráficos.html', foto_perfil=foto_perfil)
    
    
@bp.route('/carrega')
@login_required
def carrega():
       from gestaopatio.models import Agendamentos
       lista_cargas = Agendamentos.query.filter(Agendamentos.status_carga == None, Agendamentos.fim_carregamento == None).order_by(Agendamentos.entrydate, Agendamentos.entryhour).all()
       return render_template('Carrega.html', lista_cargas=lista_cargas)
    
@bp.route('/agendamentos', methods=['GET', 'POST'])
@login_required
def agendamento():
    form_agendamento = FormAgendamentos()

    if form_agendamento.validate_on_submit() and 'botao_submit_agendamento' in request.form:
        # Inicializa variável
        num_transporte = None

        # Verifica se o tipo de operação é "Recebimento"
        if form_agendamento.tipo_operacao.data == "Recebimento":
            # Busca o último número de transporte com prefixo 'D'
            ultimo_agendamento = Agendamentos.query \
                .filter(Agendamentos.num_transporte.like('D%')) \
                .order_by(Agendamentos.num_transporte.desc()) \
                .first()

            if ultimo_agendamento and ultimo_agendamento.num_transporte:
                ultimo_numero = int(ultimo_agendamento.num_transporte[1:])
                novo_numero = ultimo_numero + 1
            else:
                novo_numero = 1

            num_transporte = f'D{novo_numero:06d}'

        else:
            # Para outros tipos de operação, pode-se usar outra lógica ou deixar em branco
            num_transporte = None  # ou gerar outro padrão se necessário

        agendamento = Agendamentos(
            entrydate=form_agendamento.entrydate.data,
            entryhour=form_agendamento.entryhour.data,
            origem=form_agendamento.origem.data,
            destino=form_agendamento.destino.data,
            veiculo=form_agendamento.veiculo.data,
            cliente=form_agendamento.cliente.data,
            placa_veiculo=form_agendamento.placa_veiculo.data,
            motorista=form_agendamento.motorista.data,
            transportadora=form_agendamento.transportadora.data,
            tipo_operacao=form_agendamento.tipo_operacao.data,
            num_transporte=num_transporte,
            ultima_alteracao=datetime.utcnow(),
            usuario_alteracao=current_user.email
        )

        database.session.add(agendamento)
        database.session.commit()

        flash(f'Agendamento gerado com sucesso para: {form_agendamento.transportadora.data}', 'alert-success')
        return redirect(url_for('agendamento'))

    elif form_agendamento.validate_on_submit() and 'botao_submit_arq_agendamento' in request.form:
        return render_template('Arq_Agendamento.html')

    return render_template('Agendamento.html', form_agendamento=form_agendamento)
    

@bp.route('/arq_agenda', methods=['GET', 'POST'])
def arq_agenda():
       return render_template('Arq_Agendamento.html')
    
    
@bp.route('/arq_agenda/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'alert-warning')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'alert-warning')
            return redirect(request.url)
        if file:
            # Verificar se o arquivo já existe na tabela Arquivos
            arquivo_existente = Arquivos.query.filter_by(arquivo=file.filename).first()
            if arquivo_existente:
                flash(f'Já existe um arquivo com o nome {file.filename}', 'alert-warning')
                return redirect(request.url)
            
            try:
                agenda = pd.read_excel(file, engine='openpyxl')
                with database.session.no_autoflush:
                    for index, row in agenda.iterrows():
                        agendamento = Agendamentos.query.filter_by(num_transporte=row['Transporte']).first()
                        utc_now = datetime.utcnow()
                        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
                        local_now_a = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
                        if agendamento:
                            agendamento.num_transporte = row['Transporte']
                            agendamento.entrydate = row['Data']
                            agendamento.entryhour = row['Agenda']
                            agendamento.origem = row['Origem']
                            agendamento.destino = row['Destino']
                            agendamento.veiculo = row['Veículo']
                            agendamento.cliente = row['Cliente']
                            agendamento.placa_veiculo = row['Placa']
                            agendamento.motorista = row['Motorista']
                            agendamento.transportadora = row['Transportadora'] if 'Transportadora' in row and pd.notna(row['Transportadora']) else 'Desconhecida'
                            agendamento.tipo_operacao = "Expedição"                           
                            agendamento.ultima_alteracao = local_now_a
                            agendamento.usuario_alteracao = current_user.username
                        else:
                            novo_agendamento = Agendamentos(
                                num_transporte=row['Transporte'],
                                entrydate=row['Data'],
                                entryhour=row['Agenda'],
                                origem=row['Origem'],
                                destino=row['Destino'],
                                veiculo=row['Veículo'],
                                cliente=row['Cliente'],
                                placa_veiculo=row['Placa'],
                                motorista=row['Motorista'],
                                transportadora=row['Transportadora'] if 'Transportadora' in row and pd.notna(row['Transportadora']) else 'Desconhecida',
                                tipo_operacao="Expedição",                              
                                ultima_alteracao=local_now_a,
                                usuario_alteracao=current_user.username
                            )
                            database.session.add(novo_agendamento)
                database.session.commit()
                # Salvar informações do arquivo na tabela Arquivo
                novo_arquivo = Arquivos(
                    arquivo=file.filename,
                    ultima_alteracao=local_now_a,
                    usuario_alteracao=current_user.username
                )
                database.session.add(novo_arquivo)
                database.session.commit()
                flash(f'Arquivo {file.filename} carregado e atualizado com sucesso', 'alert-success')
            except Exception as e:
                flash(f'Erro ao processar o arquivo: {e}', 'alert-danger')
            return redirect(url_for('upload_file'))

    return render_template('Arq_Agendamento.html')

@bp.route('/buscar_transporte', methods=['POST'])
def buscar_transporte():
    num_transporte = request.form['num_transporte']
    agendamentos = get_agendamentos(num_transporte)  # Função que busca agendamentos
    vendas_me = get_vendas(num_transporte)  # Função que busca vendas
    return render_template('Documentacao.html', agendamentos=agendamentos, vendas_me=vendas_me)

def get_agendamentos(num_transporte):
    from gestaopatio.models import Agendamentos
    return Agendamentos.query.filter_by(num_transporte=num_transporte).all()

def get_vendas(num_transporte):
    return Vendas_ME.query.filter_by(num_transporte=num_transporte).all()

@bp.route('/relatorios')
@login_required
def relatorio_me():
    return render_template('Documentacao.html', agendamentos=None, vendas=None)

@bp.route('/relatorios/upload', methods=['GET', 'POST'])
def arq_produtos():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado', 'alert-warning')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'alert-warning')
            return redirect(request.url)
        if file:
            # Verificar se o arquivo já existe na tabela Arquivos
            arquivo_existente = Arquivos.query.filter_by(arquivo=file.filename).first()
            if arquivo_existente:
                flash(f'Já existe um arquivo com o nome {file.filename}', 'alert-warning')
                return redirect(request.url)
            
            try:
                vendas_me = pd.read_excel(file, engine='openpyxl')
                with database.session.no_autoflush:
                    for index, row in vendas_me.iterrows():
                        print(f"Processando linha {index}: {row}")  # Mensagem de depuração
                        vendas_me = Vendas_ME.query.filter_by(num_transporte=row['Transporte']).first()
                        data = row['Data'].to_pydatetime() if isinstance(row['Data'], pd.Timestamp) else row['Data']
                        data_producao = row['Data Produção'].to_pydatetime() if isinstance(row['Data Produção'], pd.Timestamp) else row['Data Produção']
                        if vendas_me:
                            print(f"Atualizando registro existente para transporte {row['Transporte']}")  # Mensagem de depuração
                            vendas_me.data = data
                            vendas_me.cod_cliente = row['Cód. Cliente']
                            vendas_me.cliente = row['Nome cliente']
                            vendas_me.destino = row['Cidade']
                            vendas_me.num_transporte = row['Transporte']
                            vendas_me.cod_produto = row['Cód. Produto']
                            vendas_me.descricao = row['Descrição produto']
                            vendas_me.qtd_cxf = row['Qtde CXF']
                            vendas_me.qtd_unitaria = row['Qtde UC']
                            vendas_me.transportadora = row['Transportador']
                            vendas_me.placa_veiculo = row['Placa de veículo']
                            vendas_me.centro = row['Centro']
                            vendas_me.buscar = row['Buscar']
                            vendas_me.somatoria_buscar = row['Somatória buscar']
                            vendas_me.ad_transporte = row['Ad. Transportes']
                            vendas_me.transporte_adicionar = row['Transporte + 1']
                            vendas_me.motorista = row['Motorista']
                            vendas_me.data_producao = data_producao
                            vendas_me.ultima_alteracao = datetime.now(timezone.utc)
                            vendas_me.usuario_alteracao = current_user.username
                        else:
                            print(f"Criando novo registro para transporte {row['Transporte']}")  # Mensagem de depuração
                            novo_vendas_me = Vendas_ME(
                                data=data,
                                cod_cliente=row['Cód. Cliente'],
                                cliente=row['Nome cliente'],
                                destino=row['Cidade'],
                                num_transporte=row['Transporte'],
                                cod_produto=row['Cód. Produto'],
                                descricao=row['Descrição produto'],
                                qtd_cxf=row['Qtde CXF'],
                                qtd_unitaria=row['Qtde UC'],
                                transportadora=row['Transportador'],
                                placa_veiculo=row['Placa de veículo'],
                                centro=row['Centro'],
                                buscar=row['Buscar'],
                                somatoria_buscar=row['Somatória buscar'],
                                ad_transporte=row['Ad. Transportes'],
                                transporte_adicionar=row['Transporte + 1'],
                                motorista=row['Motorista'],
                                data_producao=data_producao,
                                ultima_alteracao=datetime.now(timezone.utc),
                                usuario_alteracao=current_user.username
                            )
                            database.session.add(novo_vendas_me)
                database.session.commit()
                # Salvar informações do arquivo na tabela Arquivo
                novo_arquivo = Arquivos(
                    arquivo=file.filename,
                    ultima_alteracao=datetime.now(timezone.utc),
                    usuario_alteracao=current_user.username
                )
                database.session.add(novo_arquivo)
                database.session.commit()
                flash(f'Arquivo {file.filename} carregado e atualizado com sucesso', 'alert-success')
            except Exception as e:
                flash(f'Erro ao processar o arquivo: {e}', 'alert-danger')
            return redirect(url_for('arq_produtos'))

    return render_template('Produtos Cargas.html')

@bp.route('/reagenda', methods=['GET', 'POST'])
@login_required
def reagenda():
       agendamento_id = request.args.get('agendamento_id', type=int)
       botao_clicado = request.args.get('botao_clicado', default=None)
       agendamentos = Agendamentos.query.get_or_404(agendamento_id)
       form_reagenda = FormReagenda()

       if request.method =='GET':
            form_reagenda.num_transporte.data = agendamentos.num_transporte
            form_reagenda.entrydate.data = agendamentos.entrydate
            form_reagenda.entryhour.data = agendamentos.entryhour
            form_reagenda.origem.data = agendamentos.origem
            form_reagenda.destino.data = agendamentos.destino
            form_reagenda.veiculo.data = agendamentos.veiculo
            form_reagenda.cliente.data = agendamentos.cliente
            form_reagenda.placa_veiculo.data = agendamentos.placa_veiculo
            form_reagenda.motorista.data = agendamentos.motorista
            form_reagenda.transportadora.data = agendamentos.transportadora
            form_reagenda.tipo_operacao.data = agendamentos.tipo_operacao
       elif request.method == 'POST' and form_reagenda.validate_on_submit() and 'botao_submit_reagendar' in request.form:
           botao_clicado = 'Reagendar'
           agendamentos.status_carga='REAGENDADO'
           novo_agendamento = Agendamentos(
                num_transporte = form_reagenda.num_transporte.data,
                entrydate=form_reagenda.entrydate.data,
                entryhour=form_reagenda.entryhour.data,
                origem=form_reagenda.origem.data,
                destino=form_reagenda.destino.data,
                veiculo=form_reagenda.veiculo.data,
                cliente=form_reagenda.cliente.data,
                placa_veiculo=form_reagenda.placa_veiculo.data,
                motorista=form_reagenda.motorista.data,
                transportadora=form_reagenda.transportadora.data,
                motivo_reagenda=form_reagenda.motivo_reagenda.data,
                tipo_operacao=form_reagenda.tipo_operacao.data,
                ultima_alteracao=datetime.utcnow(), 
                usuario_alteracao=current_user.username
                )
           database.session.add(novo_agendamento)
           database.session.commit()
           flash(f'Reagendamento realizado com sucesso: {form_reagenda.transportadora.data}', 'alert-success')
           return redirect(url_for('carrega') )
       elif request.method == 'POST' and form_reagenda.validate_on_submit() and 'botao_submit_cancelar' in request.form:
           botao_clicado = 'Cancelar'
           agendamentos.status_carga='CANCELADO'
           database.session.commit()
           flash(f'Cancelamento realizado com sucesso: {form_reagenda.transportadora.data}', 'alert-success')
           return redirect(url_for('carrega') )
       elif request.method == 'POST' and form_reagenda.validate_on_submit() and 'botao_submit_alterar' in request.form:
           botao_clicado = 'Alterar'
           agendamentos.origem=form_reagenda.origem.data
           agendamentos.destino=form_reagenda.destino.data
           agendamentos.veiculo=form_reagenda.veiculo.data
           agendamentos.cliente=form_reagenda.cliente.data
           agendamentos.placa_veiculo=form_reagenda.placa_veiculo.data
           agendamentos.motorista=form_reagenda.motorista.data
           agendamentos.transportadora=form_reagenda.transportadora.data
           agendamentos.ultima_alteracao=datetime.utcnow()
           agendamentos.usuario_alteracao=current_user.username     
           database.session.commit()
           flash(f'Alteração realizado com sucesso: {form_reagenda.transportadora.data}', 'alert-success')
           return redirect(url_for('carrega') )    
       return render_template('Reagendamento.html', form_reagenda=form_reagenda, botao_clicado=botao_clicado)
    
@bp.route('/login', methods=['GET', 'POST'])
def login():
       from gestaopatio.models import Usuario
       form_login= FormLogin()
       if form_login.validate_on_submit():
           usuario = Usuario.query.filter_by(email=form_login.username.data).first()
           if usuario and bcrypt.check_password_hash(usuario.senha, form_login.senha.data):
               login_user(usuario, remember=form_login.lembrar_dados.data)
               flash(f'Login feito com sucesso para: {form_login.username.data}', 'alert-success')
               par_next = request.args.get('next')
               if par_next:
                   return redirect (par_next)
               else:    
                   return redirect(url_for('home') )
           else:
               flash(f'Falha no login! Usuario ou Senha Incorretos', 'alert-danger')
       return render_template('Login.html', form_login=form_login)
    
    
@bp.route('/acesso', methods=['GET', 'POST'])
def cadastro():
    form_conta = FormCriarConta()
    if form_conta.validate_on_submit():
        try:
            if form_conta.senha.data:
                senha_cript = bcrypt.generate_password_hash(form_conta.senha.data).decode('utf-8')
            else:
                flash('Senha não fornecida.', 'alert-danger')
                return render_template('Cadastro.html', form_conta=form_conta)

            cadastramento = Usuario(
                username=form_conta.username.data,
                email=form_conta.email.data,
                senha=senha_cript,
                hierarquia=form_conta.hierarquia_user.data,
                data_criacao=datetime.utcnow(),
                ultima_alteracao=datetime.utcnow(),
                usuario_alteracao=form_conta.username.data
            )
            database.session.add(cadastramento)
            database.session.commit()
            flash(f'Cadastro feito com sucesso para: {form_conta.username.data}', 'alert-success')
            return redirect(url_for('cadastro'))
        except Exception as e:
            app.logger.error(f'Erro ao cadastrar usuário: {e}')
            flash('Ocorreu um erro ao processar seu cadastro. Tente novamente mais tarde.', 'alert-danger')
    return render_template('Cadastro.html', form_conta=form_conta)

    
    
    
@bp.route('/entidade', methods=['GET', 'POST'])
@login_required
def entidade():
       form_cliente= FormCliente()
       form_embarcador = FormEmbarcador()
       if form_cliente.validate_on_submit() and 'botao_submit_cliente' in request.form:
           entidade = Cliente_Andina(nome_cliente = form_cliente.nome_cliente.data, 
                                      cnpj_cliente = form_cliente.cnpj_cliente.data, 
                                      cidade_cliente = form_cliente.cidade_cliente.data, 
                                      estado_cliente = form_cliente.estado_cliente.data, 
                                      operacao_cliente = form_cliente.operacao_cliente.data,
                                      ultima_alteracao=datetime.utcnow(), 
                                      usuario_alteracao=current_user.username
                                     )
           database.session.add(entidade)
           database.session.commit()
           flash(f'Cliente {form_cliente.nome_cliente.data} cadastrado com sucesso', 'alert-success')
           return redirect(url_for('entidade') )
       if form_embarcador.validate_on_submit() and 'botao_submit_embarcador' in request.form:
           entidade = Embarcador_Andina(nome_embarcador = form_embarcador.nome_embarcador.data, 
                                         cnpj_embarcador = form_embarcador.cnpj_embarcador.data, 
                                         cidade_embarcador = form_embarcador.cidade_embarcador.data, 
                                         estado_embarcador = form_embarcador.estado_embarcador.data, 
                                         ultima_alteracao=datetime.utcnow(), 
                                         usuario_alteracao=current_user.username
                                        )
           database.session.add(entidade)
           database.session.commit()
           flash(f'Embarcador {form_cliente.nome_embarcador.data} cadastrado com sucesso', 'alert-success')
           return redirect(url_for('entidade') )    
       return render_template('Cadastro_entidades.html', form_cliente=form_cliente, form_embarcador=form_embarcador)
    
@bp.route('/check_in/', methods=['GET', 'POST'])
def check_in():
    agendamento_id = request.args.get('agendamento_id', type=int)
    agendamentos_c = Agendamentos.query.get_or_404(agendamento_id)

    utc_now = datetime.utcnow()
    utc_aware = pytz.utc.localize(utc_now)  # Corrige o timezone
    local_tz = pytz.timezone('America/Sao_Paulo')
    local_now = utc_aware.astimezone(local_tz)

    agendamentos_c.check_in = local_now
    agendamentos_c.fase_carga = "CHECK-IN"
    database.session.commit()

    flash('Check-In realizado com sucesso!', 'alert-success')
    return redirect(url_for('painel'))

@bp.route('/entrada_patio/', methods=['GET', 'POST'])
def entrada_patio():
        agendamento_id = request.args.get('agendamento_id', type=int)
        agendamentos_e = Agendamentos.query.get_or_404(agendamento_id)
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_e = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        agendamentos_e.entrada_patio = local_now_e
        agendamentos_e.fase_carga = "EM PATIO"
        database.session.commit()
        flash('Entrada pátio realizado com sucesso!', 'alert-success')
        return redirect(url_for('painel'))
    
@bp.route('/inicio_carga/', methods=['GET', 'POST'])
def inicio_carga():
        agendamento_id = request.args.get('agendamento_id', type=int)
        agendamentos_i = Agendamentos.query.get_or_404(agendamento_id)
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_i = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        agendamentos_i.carregamento = local_now_i
        agendamentos_i.fase_carga = "CARREGANDO"
        database.session.commit()
        flash('Inicio de operação realizado com sucesso!', 'alert-success')
        return redirect(url_for('painel'))
    
@bp.route('/fim_carga/', methods=['GET', 'POST'])
def fim_carga():
        agendamento_id = request.args.get('agendamento_id', type=int)
        agendamentos_f = Agendamentos.query.get_or_404(agendamento_id)
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_f = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        agendamentos_f.fim_carregamento = local_now_f
        agendamentos_f.fase_carga = "CONCLUIDO"
        database.session.commit()
        flash('Operação concluída com sucesso!', 'alert-success')
        return redirect(url_for('painel'))
    
@bp.route('/saida_portaria/', methods=['GET', 'POST'])
def saida_portaria():
        agendamento_id = request.args.get('agendamento_id', type=int)
        agendamentos_s = Agendamentos.query.get_or_404(agendamento_id)
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_s = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        agendamentos_s.saida_portaria = local_now_s
        agendamentos_s.fase_carga = "EM ROTA"
        database.session.commit()
        flash('Saída portaria realizado com sucesso!', 'alert-success')
        return redirect(url_for('painel'))


@bp.route('/controle_faixa', methods=['GET', 'POST'])
def controle_faixa():
        form_gestao_patio = FormControlFaixa()
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_f = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        if form_gestao_patio.validate_on_submit():
           gestao_patio = Control_Patio(data = datetime.utcnow(),
                                      num_transporte = form_gestao_patio.num_transporte.data, 
                                      num_frota =form_gestao_patio.num_frota.data,
                                      num_faixa = form_gestao_patio.num_faixa.data,
                                      num_doca = form_gestao_patio.num_doca.data,
                                      sub_frota = form_gestao_patio.sub_frota.data,
                                      num_posicao = form_gestao_patio.num_posicao.data,  
                                      status_frota = 'Patio',
                                      hora_patio= local_now_f,  
                                      ultima_alteracao=datetime.utcnow(), 
                                      usuario_alteracao=current_user.username
                                       )
           database.session.add(gestao_patio)
           database.session.commit()
           flash(f'Frota cadastrada com sucesso para: {form_gestao_patio.num_frota.data}', 'alert-success')
           return redirect(url_for('painel_rota') )

        return render_template('Control Patio.html', form_gestao_patio=form_gestao_patio)


@bp.route('/controle_patio', methods=['GET', 'POST'])
def controle_patio():
    from gestaopatio.models import Control_Patio
    control_patio_id = request.args.get('control_patio_id', type=int)
    controles = Control_Patio.query.get_or_404(control_patio_id)
    form_gestao_patio = FormControlPatio()

    if request.method == 'GET':
        form_gestao_patio.num_transporte.data = controles.num_transporte
        form_gestao_patio.num_frota.data = controles.num_frota
        form_gestao_patio.num_faixa.data = controles.num_faixa
        form_gestao_patio.num_doca.data = controles.num_doca
        form_gestao_patio.num_posicao.data = controles.num_posicao
        form_gestao_patio.sub_frota.data = controles.sub_frota

    elif request.method == 'POST' and form_gestao_patio.validate_on_submit():
        # Obter data atual no fuso horário local
        local_tz = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(local_tz).date()

        # Verificar se já existe uma doca ocupada hoje com status 'Stage'
        doca_ocupada = Control_Patio.query.filter(
            Control_Patio.num_doca == form_gestao_patio.num_doca.data,
            Control_Patio.status_frota != 'Finalizada',
            func.date(Control_Patio.data) == hoje,
            Control_Patio.id != control_patio_id
        ).first()

        if doca_ocupada:
            flash(f'A doca {form_gestao_patio.num_doca.data} já está ocupada hoje por outra frota em status "Stage".', 'alert-danger')
            return render_template('Control Patio.html', form_gestao_patio=form_gestao_patio)

        # Atualiza os dados normalmente
        utc_now = datetime.utcnow()
        local_now_f = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)

        controles.num_transporte = form_gestao_patio.num_transporte.data
        controles.num_frota = form_gestao_patio.num_frota.data
        controles.num_faixa = form_gestao_patio.num_faixa.data
        controles.num_doca = form_gestao_patio.num_doca.data
        controles.num_posicao = form_gestao_patio.num_posicao.data
        controles.sub_frota = form_gestao_patio.sub_frota.data

        if form_gestao_patio.num_faixa.data and str(form_gestao_patio.num_faixa.data).strip():
            controles.status_frota = 'Faixa'
            controles.hora_faixa = local_now_f
        else:
            controles.status_frota = 'Stage'
            controles.hora_faixa = local_now_f

        controles.ultima_alteracao = local_now_f
        controles.usuario_alteracao = current_user.username

        database.session.commit()
        flash(f'Frota alterada com sucesso para: {form_gestao_patio.num_frota.data}', 'alert-success')
        return redirect(url_for('painel_rota'))

    return render_template('Control Patio.html', form_gestao_patio=form_gestao_patio)




@bp.route('/carregar_frota', methods=['GET', 'POST'])
def carregar_frota():
        from gestaopatio.models import Control_Patio
        control_patio_id = request.args.get('control_patio_id', type=int)
        controles = Control_Patio.query.get_or_404(control_patio_id)
        controles.status_faixa = 'Carregando'
        controles.status_frota = 'Carregando'
        database.session.commit()
        flash(f'Frota em carregamento', 'alert-success')
        return redirect(url_for('painel_rota'))


@bp.route('/concluir_faixa', methods=['GET', 'POST'])
def concluir_faixa():
        from gestaopatio.models import Control_Patio
        control_patio_id = request.args.get('control_patio_id', type=int)
        controles = Control_Patio.query.get_or_404(control_patio_id)
        utc_now = datetime.utcnow()
        local_tz = pytz.timezone('America/Sao_Paulo')  # Ajuste para o seu fuso horário local
        local_now_f = utc_now.replace(tzinfo=pytz.utc).astimezone(local_tz)
        controles.hora_conclusao = local_now_f
        controles.status_faixa = 'Liberada'
        controles.status_frota = 'Finalizada'
        database.session.commit()
        flash(f'Frota finalizada', 'alert-success')
        return redirect(url_for('painel_rota'))

@bp.route('/arq_picking', methods=['GET', 'POST'])
def arq_picking():
    if request.method == 'POST':
        try:
            conferencia_file = request.files.get('conferencia_file')
            pallet_c_file = request.files.get('pallet_c_file')
            
            if not conferencia_file or not pallet_c_file:
                flash("Arquivos necessários não encontrados.", 'alert-danger')
                return redirect(url_for('arq_picking'))
            
            conferencia_df = pd.read_excel(conferencia_file, engine='openpyxl')
            pallet_c_df = pd.read_excel(pallet_c_file, engine='openpyxl')
            
            pallet_c_df = pallet_c_df[['Zona', 'Número de Ticket', 'Pickeador', 'F', 'Hora de confirmação do ticket']]
            pallet_c_df.rename(columns={'Zona':'Posicao', 'F': 'Tipo_Palete', 'Hora de confirmação do ticket': 'Hora_Confirmação'}, inplace=True)
            
            merged_df = conferencia_df.merge(pallet_c_df, left_on='Etiqueta UD', right_on='Número de Ticket', how='left')
            merged_df.drop(columns=['Número de Ticket'], inplace=True)
            
            save_to_database(merged_df)
            flash('Arquivos carregados, mesclados e dados salvos com sucesso', 'alert-success')
        except Exception as e:
            flash(f'Erro ao processar o arquivo: {e}', 'alert-danger')
        return redirect(url_for('arq_picking'))
    
    return render_template('Dados Picking.html')

def convert_to_time(time_value):
    if pd.isna(time_value):
        return time(0, 0)  # Substitua por um valor padrão adequado
    if isinstance(time_value, float):
        hours, minutes = divmod(time_value * 60, 60)
        return time(int(hours), int(minutes))
    return time_value

def combine_date_time(date_value, time_value):
    time_value = convert_to_time(time_value)
    return datetime.combine(date_value, time_value)

def save_to_database(merged_df):
    from gestaopatio.models import ControlPicking
    # Limpar a tabela ControlPicking antes de inserir novos dados
    ControlPicking.query.delete()
    database.session.commit()    
    for index, row in merged_df.iterrows():
            atualizacao= ControlPicking(data_doc=pd.to_datetime(row['Data do documento']),
            hora_conf_piso=combine_date_time(pd.to_datetime(row['Data do documento']), row['Hora fim conf. piso']),
            hora_checkout=combine_date_time(pd.to_datetime(row['Data do documento']), row['Hora fim Check Out']),
            data_remessa=pd.to_datetime(row['Data remessa']),
            num_palete=row['Número de Palete'],
            conf_checkout=row['Conferente Checkout'],
            conf_piso=row['Conferente Piso'],
            tipo_remessa=row['Tipo de transporte'],
            num_transporte=row['Nº transporte'],
            num_remessa=row['Fornecimento'],
            material=row['Material'],
            descricao=row['Texto breve material'],
            qtd_remessa=row['Qtd.remessa'],
            num_UD=row['Etiqueta UD'] if pd.notna(row['Etiqueta UD']) else 'N/A',  # Substitua por um valor padrão adequado
            status_material=row['Descrição status'],
            num_posicao=row['Posicao'] if pd.notna(row['Posicao']) else 'N/A',  # Substitua por um valor padrão adequado
            pickeador=row['Pickeador'] if pd.notna(row['Pickeador']) else 'N/A',  # Substitua por um valor padrão adequado
            tipo_palete=row['Tipo_Palete'] if pd.notna(row['Tipo_Palete']) else 'N/A',  # Substitua por um valor padrão adequado
            hora_confirmacao=combine_date_time(pd.to_datetime(row['Data do documento']), row['Hora_Confirmação']),
            ultima_alteracao=datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/Sao_Paulo')),
            usuario_alteracao=current_user.username)
            database.session.add(atualizacao)
    database.session.commit()


@bp.route('/sair')
@login_required
def sair():
       logout_user()
       flash(f'Logout feito com sucesso!', 'alert-success')
       return redirect(url_for('home') )
