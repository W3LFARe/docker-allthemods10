# Kubernetes Example

## Disclaimer

Your mileage may vary depending on what storage you're using for your k8s cluster. This is not an officially supported method of orchastrating this container as it is designed for Docker in Unraid. 

This was provided from a member of the community and their intentions was to give you a starting point if you found yourself here looking to try to use this container in k8s. 

Remeber to either set nodeports manually or go get the assigment from your service so that you can properly port forward. 

## Example Manifest

apiVersion: v1
kind: Service
metadata:
  name: minecraft-all-the-mods-10
  labels:
    app: minecraft-all-the-mods-10
spec:
  type: NodePort
  ports:
  - port: 19565
    protocol: TCP
    name: "metrics"
    targetPort: "metrics"
  - port: 25575
    protocol: TCP
    name: "minecraft-rcon"
    targetPort: "minecraft-rcon"
  - port: 25565
    protocol: TCP
    name: "minecraft-game"
    targetPort: "minecraft-game"
  selector:
    app: minecraft-all-the-mods-10
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: minecraft-all-the-mods-10
  namespace: default
spec:
  selector:
    matchLabels:
      app: minecraft-all-the-mods-10
  template:
    metadata:
      labels:
        app: minecraft-all-the-mods-10
    spec:
      initContainers:
        - name: volume-ownership
          image: busybox
          command: ["sh", "-c", "chown -R 99:100 /data"]
          volumeMounts:
            - name: minecraft-data
              mountPath: /data
      containers:
        - name: minecraft-all-the-mods-10
          image: w3lfare/allthemods10:latest  # Or specific version if needed
          env:
            - name: EULA
              value: "true"
            - name: JVM_OPTS
              value: "-Xms8192m -Xmx12288m"
            - name: MOTD
              value: "Hello World!"
            - name: ENABLE_WHITELIST
              value: "false"
            - name: WHITELIST_USERS
              value: USERNAME
            - name: OP_USERS
              value: USERNAME
            - name: ALLOW_FLIGHT
              value: "false"
            - name: ONLINE_MODE
              value: "true"
          ports:
            - name: minecraft-game
              containerPort: 25565  # Expose port 25565
            - name: minecraft-rcon
              containerPort: 25575
            - name: metrics
              containerPort: 19565
          resources:
            requests:
              cpu: 4  
              memory: "16Gi"  
            limits:
              cpu: 6  
              memory: "16Gi" 
          volumeMounts:
          - name: minecraft-data
            mountPath: /data
      volumes:
        - name: minecraft-data
          persistentVolumeClaim:
            claimName: minecraft-data
  volumeClaimTemplates:
  - metadata:
      name: minecraft-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 50Gi