  /* Horizonte de sucesos — fondo de marca botmexico.net.
     Adaptado del concepto de agujero negro/disco de acreción, SIN campo estelar
     (eso era el "look espacial" que no queremos) y recoloreado verde/blanco/rojo MX.
     Falla silenciosa: si WebGL no está disponible, el canvas se oculta y queda
     el fondo CSS (radial-gradients) como base — cero riesgo para el resto de la página. */
  (function () {
    try {
      if (typeof THREE === 'undefined') return;
      const cv = document.getElementById('horizon');
      if (!cv) return;
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.setSize(innerWidth, innerHeight);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, .1, 400);
      camera.position.set(0, 1.9, 12.4);
      camera.lookAt(0, 0, 0);

      const C_HOT = new THREE.Color(0xf0f6fc);   // núcleo blanco
      const C_MID = new THREE.Color(0x3fb950);   // verde marca
      const C_OUT = new THREE.Color(0x2ea043);   // verde profundo
      const C_RIM = new THREE.Color(0xef4a45);   // glint rojo en el borde (Doppler)

      const hole = new THREE.Mesh(new THREE.SphereGeometry(1.62, 48, 48), new THREE.MeshBasicMaterial({ color: 0x0b0e12 }));
      hole.renderOrder = 2; scene.add(hole);

      const shadow = new THREE.Mesh(
        new THREE.SphereGeometry(1.78, 48, 48),
        new THREE.ShaderMaterial({
          transparent: true, side: THREE.BackSide, depthWrite: false,
          vertexShader: `varying vec3 vN; varying vec3 vP;
            void main(){ vN=normalize(normalMatrix*normal); vP=(modelViewMatrix*vec4(position,1.)).xyz;
              gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
          fragmentShader: `varying vec3 vN; varying vec3 vP;
            void main(){ float f = 1.0 - abs(dot(normalize(vN), normalize(-vP)));
              gl_FragColor = vec4(0.043,0.055,0.07, pow(f,1.4)*.95); }`
        })
      );
      shadow.renderOrder = 3; scene.add(shadow);

      const R_IN = 2.28, R_OUT = 7.2;
      const diskUniforms = {
        uTime: { value: 0 }, uEnergy: { value: 0 }, uInner: { value: R_IN }, uOuter: { value: R_OUT },
        cHot: { value: C_HOT }, cMid: { value: C_MID }, cOut: { value: C_OUT }, cRim: { value: C_RIM }
      };
      const diskMat = () => new THREE.ShaderMaterial({
        uniforms: diskUniforms, transparent: true, side: THREE.DoubleSide,
        depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: `
          varying float vR; varying float vA;
          uniform float uInner, uOuter;
          void main(){
            float r = length(position.xy);
            vR = (r - uInner) / (uOuter - uInner);
            vA = atan(position.y, position.x);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
          }`,
        fragmentShader: `
          varying float vR; varying float vA;
          uniform float uTime, uEnergy, uInner, uOuter;
          uniform vec3 cHot, cMid, cOut, cRim;
          float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
          float noise(vec2 p){
            vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.0-2.0*f);
            return mix(mix(hash(i),hash(i+vec2(1,0)),u.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),u.x), u.y);
          }
          float fbm(vec2 p){ float v=0.,a=.5; for(int i=0;i<5;i++){ v+=a*noise(p); p*=2.07; a*=.5; } return v; }
          void main(){
            float rAbs = uInner + vR*(uOuter-uInner);
            float omega = 5.0 * pow(rAbs, -1.5);
            float a = vA + uTime * omega;
            vec2 q = vec2(a*2.35, vR*7.0 - uTime*0.09);
            float t = fbm(q) * .62 + fbm(q*2.9 + 11.0) * .38;
            float bands = .58 + .42*t;
            float temp = pow(1.0 - vR, 1.65);
            vec3 col = mix(cOut, cMid, smoothstep(.10,.62,temp));
            col = mix(col, cHot, smoothstep(.74,1.0,temp));
            float beam = 1.0 + 0.85 * sin(vA);
            float beamPos = clamp(sin(vA), 0.0, 1.0);
            col = mix(col, cRim, beamPos * 0.30 * (1.0 - temp));
            beam = clamp(beam, .20, 1.95);
            float glow = pow(1.0 - vR, 2.35) * 1.5 + .12;
            float alpha = smoothstep(0.0,.075,vR) * (1.0 - smoothstep(.62,1.0,vR));
            alpha *= bands * glow * (.72 + .5*uEnergy) * beam;
            gl_FragColor = vec4(col * (bands*.55 + .55) * beam, alpha);
          }`
      });

      const ringGeo = new THREE.RingGeometry(R_IN, R_OUT, 220, 60);
      const TILT = -Math.PI / 2 + 0.235;
      const disk = new THREE.Mesh(ringGeo, diskMat());
      disk.rotation.x = TILT; disk.renderOrder = 1; scene.add(disk);

      const lensGroup = new THREE.Group();
      const lens = new THREE.Mesh(ringGeo, diskMat());
      lens.rotation.x = TILT; lens.renderOrder = 4;
      lensGroup.add(lens); lensGroup.rotation.z = Math.PI / 2; scene.add(lensGroup);

      const photon = new THREE.Mesh(
        new THREE.RingGeometry(1.80, 2.02, 160),
        new THREE.ShaderMaterial({
          transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
          uniforms: { uTime: { value: 0 }, uEnergy: { value: 0 }, cHot: { value: C_HOT }, cMid: { value: C_MID } },
          vertexShader: `varying vec2 vU; varying float vA;
            void main(){ vU=uv; vA=atan(position.y,position.x);
              gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
          fragmentShader: `
            varying vec2 vU; varying float vA; uniform float uTime,uEnergy; uniform vec3 cHot,cMid;
            void main(){
              float d = abs(vU.y - .5) * 2.0;
              float core = pow(1.0 - d, 6.0);
              float beam = 1.0 + .78*sin(vA);
              float a = core * (.6 + .5*uEnergy) * clamp(beam,.22,1.85);
              gl_FragColor = vec4(mix(cMid, cHot, core*.75), a);
            }`
        })
      );
      photon.renderOrder = 5; scene.add(photon);

      const halo = new THREE.Mesh(
        new THREE.PlaneGeometry(26, 26),
        new THREE.ShaderMaterial({
          transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
          uniforms: { uEnergy: { value: 0 }, cOut: { value: C_OUT } },
          vertexShader: `varying vec2 vU; void main(){ vU=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
          fragmentShader: `varying vec2 vU; uniform float uEnergy; uniform vec3 cOut;
            void main(){ float d=length(vU-.5)*2.0;
              float a=pow(max(0.,1.0-d),3.4)*(.09+.11*uEnergy);
              gl_FragColor=vec4(cOut,a);}`
        })
      );
      halo.position.z = -3.2; halo.renderOrder = 0; scene.add(halo);

      let mx = 0, my = 0, tx = 0, ty = 0, energy = 0, target = .12;
      let paused = false;
      addEventListener('pointermove', e => {
        tx = (e.clientX / innerWidth - .5); ty = (e.clientY / innerHeight - .5);
      }, { passive: true });
      addEventListener('resize', () => {
        camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
        renderer.setSize(innerWidth, innerHeight);
      });
      window.horizonPulse = function (amount) { target = Math.min(1, target + (amount || .5)); };
      // pulso ambiental sutil al interactuar con una tarjeta — sin exponer datos del backend
      document.addEventListener('click', e => {
        if (e.target.closest('.acc-card') || e.target.closest('.match-row')) window.horizonPulse(.45);
      });

      const clock = new THREE.Clock();
      function frame() {
        if (paused) return;
        const t = clock.getElapsedTime();
        mx += (tx - mx) * .04; my += (ty - my) * .04;
        target *= .985; energy += (target - energy) * .06;

        diskUniforms.uTime.value = t; diskUniforms.uEnergy.value = energy;
        photon.material.uniforms.uTime.value = t; photon.material.uniforms.uEnergy.value = energy;
        halo.material.uniforms.uEnergy.value = energy;

        camera.position.x = Math.sin(t * .04) * .5 + mx * 1.3;
        camera.position.y = 1.9 + Math.sin(t * .03) * .16 - my * .9;
        camera.position.z = 12.4 - energy * .6;
        camera.lookAt(0, 0, 0);
        photon.quaternion.copy(camera.quaternion);
        halo.quaternion.copy(camera.quaternion);
        lensGroup.rotation.z = Math.PI / 2 + mx * .14;

        renderer.render(scene, camera);
        if (!reduce) requestAnimationFrame(frame);
      }
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) { paused = true; }
        else if (!paused) { /* already running */ }
        else { paused = false; if (!reduce) frame(); }
      });
      frame();
    } catch (e) {
      const cv = document.getElementById('horizon');
      if (cv) cv.style.display = 'none';
    }
  })();
