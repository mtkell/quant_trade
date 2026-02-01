(function(){
  let csrf = null;
  let currentUser = null;

  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  const statusDiv = document.getElementById('status');
  const feedPre = document.getElementById('feed');
  const refreshBtn = document.getElementById('refresh');
  const emergencyBtn = document.getElementById('emergency');

  const loginBtn = document.getElementById('login-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const userField = document.getElementById('login-user');
  const passField = document.getElementById('login-pass');
  const currentUserDiv = document.getElementById('current-user');

  function setUser(u){
    currentUser = u;
    currentUserDiv.textContent = u ? ('Logged in: '+u) : 'Not logged in';
  }

  async function login(){
    const user = userField.value;
    const pass = passField.value;
    try{
      const res = await fetch('/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user, pass})});
      const j = await res.json();
      if(res.ok){
        csrf = j.csrf;
        setUser(user);
        alert('Login successful');
      } else {
        alert('Login failed: '+JSON.stringify(j));
      }
    }catch(e){ alert('Login error: '+e.message); }
  }

  async function logout(){
    try{
      await fetch('/logout', {method:'POST'});
    }catch(e){}
    csrf = null;
    setUser(null);
  }

  loginBtn.addEventListener('click', login);
  logoutBtn.addEventListener('click', logout);

  function renderStatus(data){
    const m = data.metrics;
    statusDiv.innerHTML = `
      <div>Total Capital: $${m.total_capital.toLocaleString()}</div>
      <div>Available: $${m.available_capital.toLocaleString()}</div>
      <div>Deployed: $${m.deployed_capital.toLocaleString()}</div>
      <div>Active Positions: ${m.active_positions}</div>
      <div>Closed Positions: ${m.closed_positions}</div>
      <div>Realized P&L: $${m.realized_pnl.toFixed(2)}</div>
      <div>Unrealized P&L: $${m.unrealized_pnl.toFixed(2)}</div>
    `;
  }

  ws.addEventListener('open', ()=>{
    statusDiv.textContent = 'Connected, requesting status...';
    ws.send(JSON.stringify({cmd:'refresh'}));
  });

  ws.addEventListener('message', (ev)=>{
    try{
      const msg = JSON.parse(ev.data);
      if(msg.type === 'status'){
        renderStatus(msg.data);
      } else if(msg.type === 'feed'){
        const txt = JSON.stringify(msg.data);
        feedPre.textContent = txt + '\n' + feedPre.textContent;
      }
    }catch(e){
      console.error(e);
    }
  });

  refreshBtn.addEventListener('click', ()=>{
    ws.send(JSON.stringify({cmd:'refresh'}));
  });

  emergencyBtn.addEventListener('click', async ()=>{
    if(!confirm('Run emergency liquidation (demo)?')) return;
    try{
      const headers = {'Content-Type':'application/json'};
      if(csrf) headers['X-CSRF-Token'] = csrf;
      const res = await fetch('/api/emergency_liquidate', {method:'POST', headers, body:JSON.stringify({prices:{}})});
      const j = await res.json();
      alert(JSON.stringify(j));
      ws.send(JSON.stringify({cmd:'refresh'}));
    }catch(err){
      alert('Error: '+err.message);
    }
  });

  // Entry form
  const placeBtn = document.getElementById('place-entry');
  const prodInput = document.getElementById('entry-product');
  const priceInput = document.getElementById('entry-price');
  const qtyInput = document.getElementById('entry-qty');

  async function fetchPositions(){
    try{
      const res = await fetch('/api/positions');
      const j = await res.json();
      renderPositions(j.positions || []);
    }catch(e){
      document.getElementById('positions').textContent = 'Error fetching positions';
    }
  }

  function renderPositions(list){
    const container = document.getElementById('positions');
    if(!list.length){
      container.textContent = 'No active positions';
      return;
    }
    const table = document.createElement('table');
    table.style.width = '100%';
    list.forEach(p=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><a href='#' class='pos-link' data-id='${p.position_id}'>${p.product_id}</a></td><td>${p.qty}</td><td>${p.entry_price}</td><td>${p.current_pnl}</td><td><button data-id='${p.position_id}' data-prod='${p.product_id}' class='cancel-btn'>Cancel</button></td>`;
      table.appendChild(tr);
    });
    container.innerHTML = '';
    container.appendChild(table);
    Array.from(document.getElementsByClassName('cancel-btn')).forEach(btn=>{
      btn.addEventListener('click', async (ev)=>{
        const orderId = prompt('Order id / stop id to cancel (or leave blank to cancel stop associated with position):');
        const prod = btn.getAttribute('data-prod');
        const payload = { order_id: orderId, product_id: prod };
        const headers = {'Content-Type':'application/json'};
        if(csrf) headers['X-CSRF-Token'] = csrf;
        const res = await fetch('/api/cancel_order', {method:'POST', headers, body:JSON.stringify(payload)});
        const j = await res.json();
        alert(JSON.stringify(j));
        fetchPositions();
      });
    });

    Array.from(document.getElementsByClassName('pos-link')).forEach(a=>{
      a.addEventListener('click', async (ev)=>{
        ev.preventDefault();
        const id = a.getAttribute('data-id');
        const res = await fetch('/api/position/'+encodeURIComponent(id));
        const j = await res.json();
        alert(JSON.stringify(j, null, 2));
      });
    });
  }

  document.getElementById('refresh-positions').addEventListener('click', fetchPositions);
  // initial load
  fetchPositions();

  placeBtn.addEventListener('click', async ()=>{
    const product_id = prodInput.value;
    const price = priceInput.value;
    const qty = qtyInput.value;
    const headers = {'Content-Type':'application/json'};
    if(csrf) headers['X-CSRF-Token'] = csrf;
    try{
      const res = await fetch('/api/place_entry', {method:'POST', headers, body:JSON.stringify({product_id, price, qty})});
      const j = await res.json();
      alert(JSON.stringify(j));
      fetchPositions();
      ws.send(JSON.stringify({cmd:'refresh'}));
    }catch(e){
      alert('Error placing entry: '+e.message);
    }
  });

})();
