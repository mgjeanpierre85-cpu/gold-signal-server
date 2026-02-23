@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "bad_request"}), 400
  
    try:
        ticker = data.get("ticker", "GOLD").upper()
        prediction = (data.get("prediction") or data.get("model_prediction", "UNKNOWN")).upper()
        current_price = float(data.get("open_price" if "open_price" in data else "close_price", 0))
        timeframe = str(data.get("timeframe", "1"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # EL CAMBIO CLAVE: Usamos el signal_id de PineScript como identificador único
        signal_id = data.get("signal_id")
        pos_id = f"{ticker}-{signal_id}" if signal_id else f"{ticker}-{timeframe}-{time_str}"
     
        db = SessionLocal()
      
        if "EXIT" not in prediction:
            # Evitar duplicados: Si ya existe este pos_id, ignoramos
            exists = db.query(Signal).filter(Signal.position_id == pos_id).first()
            if exists:
                db.close()
                return jsonify({"status": "ignored", "reason": "duplicate"}), 200

            new_sig = Signal(
                position_id=pos_id,
                ticker=ticker,
                timeframe=timeframe,
                open_price=current_price,
                sl=float(data.get("sl", 0)),
                tp=float(data.get("tp", 0)),
                volume="0.01",
                model_prediction=prediction,
                time=time_str,
                result="PENDING"
            )
            db.add(new_sig)
            db.commit()
           
            msg = format_new_signal(ticker, prediction, current_price, new_sig.sl, new_sig.tp, timeframe, time_str)
            send_telegram(msg)
        else:
            # BUSQUEDA INTELIGENTE: Primero por signal_id, luego por ticker pendiente
            last_op = None
            if signal_id:
                last_op = db.query(Signal).filter(Signal.position_id == pos_id, Signal.result == "PENDING").first()
            
            if not last_op: # Fallback si no hay signal_id
                last_op = db.query(Signal).filter(Signal.ticker == ticker, Signal.result == "PENDING").order_by(desc(Signal.created_at)).first()
          
            if last_op:
                last_op.close_price = current_price
                if last_op.model_prediction == "BUY":
                    last_op.result = "WIN" if current_price > last_op.open_price else "LOSS"
                else:
                    last_op.result = "WIN" if current_price < last_op.open_price else "LOSS"
                
                # Cálculo de Pips Profesional (XAU=100, XAG=100)
                pips = (current_price - last_op.open_price) * 100 if last_op.model_prediction == "BUY" else (last_op.open_price - current_price) * 100
                
                db.commit()
                msg = format_close_signal(ticker, last_op.result, current_price, pips)
                send_telegram(msg)
      
        db.close()
        return jsonify({"status": "ok"}), 200
  
    except Exception as e:
        print(f"Error en predict: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400
